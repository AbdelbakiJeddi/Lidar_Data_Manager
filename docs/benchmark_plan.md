# Query Performance Benchmark: Tiled vs Monolithic Extraction

## Goal
Determine if the "tiling" architecture actually provides a faster extraction experience for the end-user when selecting a specific zone, compared to cropping from the original large dataset.

---

## The Comparison

### Strategy A: Tiled Extraction (Current)
1. **Lookup**: Query MongoDB for tiles overlapping the Test Zone.
2. **Download**: Download only those specific tiles from MinIO.
3. **Process**: Crop each tile and merge into final LAZ.

### Strategy B: Monolithic Extraction (Naive)
1. **Download**: Download the **entire** original LAZ file (e.g., 2GB).
2. **Process**: Run `pdal crop` on the entire file to get the Test Zone.

---

## User Review Required

> [!IMPORTANT]
> The biggest difference here is usually **Network/IO**. Tiling avoids downloading gigabytes of data that are outside the selected zone. For a small zone extraction, tiling should be vastly superior.

---

## Benchmark Script: `benchmark_query.sh`

The script will:
1. **Preparation**:
    - Ensure `merged_dataset_2gb_final.laz` (Original) is available.
    - Ensure a processed version (Tiles) is available in MinIO/DB.
2. **Define Test Zone**:
    - Pick a rectangular area covering ~10% of the dataset.
3. **Execute Scenario A (Tiled)**:
    - Simulate the `POST /lidar/tiles/extract-zone` logic.
    - Measure: `DB Query + Tile Downloads + Crop/Merge Time`.
4. **Execute Scenario B (Monolithic)**:
    - Simulate a naive extraction.
    - Measure: `Full File Download + Full File Crop Time`.
5. **Results**:
    - Compare total "Time to Download" for the user.

---

## Verification Plan

1. **Run Benchmark**: Execute `./benchmark_query.sh`.
2. **Vary Zone Size**: Test with a "Tiny Zone" (1% area) and a "Large Zone" (50% area).
3. **Report**: Present a table showing where the "break-even" point is.
