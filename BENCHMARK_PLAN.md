# LiDAR Extraction Benchmark Plan

This document outlines the strategy for comparing the performance of spatial zone extraction using two different architectures: **Tiled (Current)** vs **Monolithic (Naive)**.

## 1. Objective
Quantify the performance gain (or loss) of the tiling architecture when a user requests a specific spatial zone (e.g., a 100m x 100m area) from a large 2GB+ dataset.

---

## 2. Methodology

### Scenario A: Tiled Extraction (The "Smart" Way)
1. **Index Lookup**: Query MongoDB for tiles overlapping the request bounding box.
2. **Selective Download**: Download only the relevant tiles from MinIO storage.
3. **Parallel Crop**: Crop each individual tile using PDAL.
4. **Merge**: Combine the cropped tiles into the final result.

### Scenario B: Monolithic Extraction (The "Naive" Way)
1. **Full Download**: Download the entire original 2GB LAZ file from MinIO.
2. **Global Crop**: Run `pdal crop` on the entire file to extract the request bounding box.

---

## 3. Metrics to Measure
- **Network I/O Time**: Time spent downloading data from MinIO.
- **Processing Time**: Time spent by PDAL on cropping and merging.
- **Peak RAM Usage**: Maximum memory consumption during the extraction.
- **Total Request Latency**: Total time from request start to result ready.

---

## 4. Test Scenarios
We will test three different selection sizes to find the "break-even" point:
1. **Small Selection**: ~1% of the total dataset area.
2. **Medium Selection**: ~10% of the total dataset area.
3. **Large Selection**: ~50% of the total dataset area.

---

## 5. Hypothesis
We expect the **Tiled** approach to be significantly faster for small and medium selections because it avoids the massive I/O bottleneck of downloading parts of the file that are not needed. The **Monolithic** approach might only be competitive when the user requests a very large percentage of the total area.
