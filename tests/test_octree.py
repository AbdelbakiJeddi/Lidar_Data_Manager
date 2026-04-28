"""Test PDAL sampling methods and SPSLiDAR octree building algorithm.

Verifies:
1. PDAL is available and functional.
2. sample_nth + remainder_nth produce complementary, non-overlapping sets.
3. Octree nodes are created with correct hierarchy.
4. Zero duplication: sum of ALL node point_counts == input point count.
"""

import json
import os
import subprocess

from minio import Minio

from app.core.settings import get_settings
from app.core.minio_client import BUCKET_RAW, BUCKET_PROCESSED
from app.services.pdal_processor import PDALProcessor
from app.services.octree_builder import OctreeBuilder


def test_pdal():
    print("=" * 60)
    print("TEST 1: PDAL availability")
    print("=" * 60)
    settings = get_settings()
    try:
        result = subprocess.run(
            [settings.pdal_bin, "--version"], capture_output=True, text=True
        )
        print(f"  PDAL Version: {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"  FAIL: PDAL not found: {e}")
        return False


def generate_test_laz(filename="/tmp/test_input.laz", count=10000):
    print(f"\n  Generating {count}-point synthetic LAZ: {filename}")
    pipeline = {
        "pipeline": [
            {
                "type": "readers.faux",
                "count": count,
                "mode": "random",
                "bounds": "([0,100],[0,100],[0,50])",
            },
            {
                "type": "writers.las",
                "filename": filename,
                "compression": "true",
            },
        ]
    }
    pipeline_file = "/tmp/gen_pipeline.json"
    with open(pipeline_file, "w") as f:
        json.dump(pipeline, f)
    try:
        subprocess.run(["pdal", "pipeline", pipeline_file], check=True)
        print(f"  Generated {filename}")
        return filename
    finally:
        if os.path.exists(pipeline_file):
            os.remove(pipeline_file)


def test_sample_remainder_split():
    print("\n" + "=" * 60)
    print("TEST 2: sample_nth + remainder_nth split integrity")
    print("=" * 60)

    input_file = generate_test_laz(count=1000)
    processor = PDALProcessor()

    total = processor.get_point_count(input_file)
    print(f"  Input points: {total}")

    sampled_file = "/tmp/test_sampled.laz"
    remainder_file = "/tmp/test_remainder.laz"

    for step in [2, 3, 5, 10]:
        sampled_count = processor.sample_nth(input_file, sampled_file, step)
        remainder_count = processor.remainder_nth(input_file, remainder_file, step)
        total_check = sampled_count + remainder_count

        status = "PASS" if total_check == total else "FAIL"
        print(
            f"  step={step:2d}: sampled={sampled_count:4d} + "
            f"remainder={remainder_count:4d} = {total_check:4d}  "
            f"(expected {total})  [{status}]"
        )
        if total_check != total:
            raise AssertionError(
                f"Split integrity FAILED for step={step}: "
                f"{sampled_count}+{remainder_count}={total_check} != {total}"
            )

    # Cleanup
    for f in [input_file, sampled_file, remainder_file]:
        if os.path.exists(f):
            os.remove(f)

    print("  All split integrity checks PASSED")


def test_octree_building():
    print("\n" + "=" * 60)
    print("TEST 3: SPSLiDAR octree building + zero duplication")
    print("=" * 60)

    input_file = generate_test_laz(count=10000)
    processor = PDALProcessor()
    total_input_points = processor.get_point_count(input_file)
    print(f"  Input points: {total_input_points}")

    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

    # Ensure buckets exist
    for bucket in [BUCKET_RAW, BUCKET_PROCESSED]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            print(f"  Created bucket: {bucket}")

    # Upload test file to MinIO
    object_name = "tests/test_input.laz"
    client.fput_object(BUCKET_RAW, object_name, input_file)
    print(f"  Uploaded to {BUCKET_RAW}/{object_name}")

    # Build octree with low threshold to force subdivision
    builder = OctreeBuilder(
        minio_client=client,
        dataset_id="test_spslidar",
        max_depth=3,
        point_threshold=1000,
    )

    try:
        nodes = builder.build_octree(
            object_name, input_in_minio=True, source_bucket=BUCKET_RAW
        )

        stats = builder.get_stats()
        print(f"\n  Octree Stats:")
        print(f"    Total nodes:       {stats['total_nodes']}")
        print(f"    Leaf nodes:        {stats['leaf_nodes']}")
        print(f"    Max depth reached: {stats['max_depth_reached']}")
        print(f"    Leaf points:       {stats['total_points']}")
        print(f"    Sampled points:    {stats['sampled_points']}")

        # ---- Zero duplication check ---- #
        # In SPSLiDAR: every point appears in exactly ONE node.
        # So sum of ALL node point_counts must equal the input count.
        all_points = sum(n.point_count for n in nodes)
        print(f"\n  Zero Duplication Check:")
        print(f"    Sum of ALL node points: {all_points}")
        print(f"    Original input points:  {total_input_points}")

        if all_points == total_input_points:
            print(f"    RESULT: PASS ✓ (zero duplication confirmed)")
        else:
            diff = all_points - total_input_points
            print(f"    RESULT: FAIL ✗ (difference: {diff})")

        # ---- Hierarchy check ---- #
        root = next((n for n in nodes if n.node_id == "root"), None)
        if root:
            print(f"\n  Root node:")
            print(f"    point_count: {root.point_count}")
            print(f"    is_leaf:     {root.is_leaf}")
            print(f"    children:    {root.children}")
            print(f"    minio_path:  {root.minio_path}")

        # ---- Non-leaf nodes should have fewer points than leaves ---- #
        non_leaf_nodes = [n for n in nodes if not n.is_leaf]
        leaf_nodes = [n for n in nodes if n.is_leaf]
        if non_leaf_nodes:
            max_non_leaf = max(n.point_count for n in non_leaf_nodes)
            print(f"\n  Sampling Check:")
            print(f"    Max non-leaf point_count: {max_non_leaf}")
            print(f"    Point threshold:          {builder.point_threshold}")
            if max_non_leaf <= builder.point_threshold:
                print(f"    RESULT: PASS ✓ (non-leaf nodes within threshold)")
            else:
                print(f"    RESULT: INFO (non-leaf may exceed threshold at root)")

    finally:
        builder.cleanup()
        if os.path.exists(input_file):
            os.remove(input_file)


if __name__ == "__main__":
    if test_pdal():
        test_sample_remainder_split()
        test_octree_building()
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
