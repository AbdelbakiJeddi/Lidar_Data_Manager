You are writing a LaTeX PFE (academic thesis) report for a Computer Science student at a Tunisian university. The project is a LiDAR Data Management System where a survey lab uploads datasets and other users retrieve data through a web app with an interactive map. The storage backend uses MinIO (S3-compatible object storage), with an automated split tiling and compression pipeline for point cloud data.

Write the full LaTeX source code for this report following EXACTLY this structure:

DOCUMENT SETUP:
- Use documentclass report with 12pt, a4paper
- Packages: geometry, inputenc (utf8), fontenc (T1), graphicx, hyperref, booktabs, longtable, array, xcolor, titlesec, fancyhdr, setspace, parskip, listings, float, amsmath, biblatex (backend=biber)
- Margins: top=2.5cm, bottom=2.5cm, left=3cm, right=2.5cm
- One and a half line spacing
- Custom chapter and section title formatting using titlesec (dark blue color #1F3864)

STRUCTURE TO IMPLEMENT:

1. Title page:
   - University name (leave placeholder)
   - Department: Computer Science / Software Engineering
   - Report type: Final Year Project (PFE)
   - Title: LiDAR Research Lab Backbone — A Centralized LiDAR Data Management Platform
   - Author: (leave placeholder)
   - Supervisor: (leave placeholder)
   - Academic year: 2024/2025

2. Front matter pages (each on its own page):
   - Supervisor appreciation page (blank box for signature)
   - Acknowledgements page (placeholder text)
   - Abstract page (English) — write a proper abstract describing the system: MinIO storage, tiling pipeline, compression, web app with map-based spatial query
   - Keywords page: LiDAR, Point Cloud, MinIO, S3 Storage, Spatial Tiling, Data Management, Web Application, GIS
   - Table of contents
   - List of figures
   - List of tables
   - Acronyms page: LiDAR, LAZ, LAS, S3, GIS, API, GUI, REST, MinIO, UML, MVC

3. Chapter 1 — Introduction:
   Keep this chapter SHORT and clean like a professional PFE.
   Sections:
   1.1 Context of the Study — 1 paragraph on LiDAR adoption in survey labs
   1.2 Problem Statement — 1 paragraph on scattered storage, no centralized access
   1.3 Aims and Objectives — bullet list of 5 objectives (centralized storage, tiling pipeline, map-based retrieval, multi-role access, scalability)
   1.4 Proposed Solution and Results — 3-4 lines summarizing what was built and that it works
   1.5 Structure of the Report — one paragraph describing all 5 chapters

4. Chapter 2 — Literature Review:
   Sections:
   2.1 Technical Background — explain LiDAR technology, point clouds (LAS/LAZ format), object storage (S3), spatial tiling, data compression. Each concept in its own subsection.
   2.2 Related Works — write a table (using booktabs) comparing at least 5 existing systems/approaches: Potree, SPSLiDAR, ArcGIS Online, OpenTopography, Cesium ion. Columns: System, Storage Approach, Access Method, Limitations.
   2.3 Findings and Contribution — paragraph on the gap and what this project contributes

5. Chapter 3 — Analysis and Specification of Requirements:
   Sections:
   3.1 Requirement Analysis:
      3.1.1 Actors Identification — two actors: Lab Staff (data producer) and Researcher (data consumer)
      3.1.2 Functional Requirements — list FR for each actor (upload dataset, trigger pipeline, browse map, select zone, download subset, manage users)
      3.1.3 Non-Functional Requirements — performance, scalability, reliability, usability, security, interoperability
   3.2 Requirements Specification:
      3.2.1 Modeling Language — short paragraph on UML
      3.2.2 Use Case Diagram — include \begin{figure} placeholder with caption
      3.2.3 Sequence Diagrams — include 3 figure placeholders: Upload Dataset, Spatial Query and Download, Authentication

6. Chapter 4 — Conception:
   Sections:
   4.1 General Conception:
      4.1.1 Logical Architecture — describe MVC or layered architecture, include figure placeholder
      4.1.2 Physical Architecture — describe client-server model with MinIO, backend API, frontend web app. Include figure placeholder.
   4.2 Detailed Conception:
      4.2.1 Activity Diagram — figure placeholder
      4.2.2 Class Diagram — figure placeholder
      4.2.3 Database/Storage Schema — describe how datasets and tiles are organized in MinIO buckets

7. Chapter 5 — Implementation and Results:
   Sections:
   5.1 Environment and Working Tools:
      5.1.1 Hardware Environment — placeholder table
      5.1.2 Software Environment — list tools (VS Code, GitHub, Overleaf, Postman, etc.)
   5.2 Technological Choices:
      5.2.1 Backend — describe the API framework choice
      5.2.2 Storage — describe MinIO and S3 compatibility
      5.2.3 Processing Pipeline — describe tiling and compression tools (PDAL or similar)
      5.2.4 Frontend — describe the web app and map library (Leaflet or OpenLayers)
   5.3 Implementation:
      5.3.1 Data Ingestion Pipeline — describe upload to tiling to compression to MinIO storage flow, include figure placeholder
      5.3.2 Spatial Query and Retrieval — describe how the map selection triggers backend query and returns tiles
      5.3.3 Web Application Interface — describe key screens, include figure placeholders for: Map View, Upload Form, Download Result
   5.4 Results and Evaluation — describe what was tested and that the system works, include a placeholder results table

8. Conclusion and Perspectives:
   - Summary paragraph of what was achieved
   - Paragraph on future work (real-time streaming, mobile app, access analytics)

9. Bibliography:
   - Use biblatex with \printbibliography
   - Add at least 8 real and plausible references for LiDAR data management, point cloud processing, MinIO/S3, web GIS (use realistic author names, titles, years between 2018-2024)

WRITING RULES:
- All text must be in proper academic English
- Every chapter must start with a brief introductory paragraph before the first section
- Every chapter must end with a short conclusion paragraph
- Use \label and \ref consistently for all figures, tables, and chapters
- All figures use \begin{figure}[H] with \centering, a descriptive \caption, and a \label
- Do not use placeholder text like "Lorem ipsum" — write real academic content appropriate for a LiDAR data management system PFE
- The tone must match a Computer Science engineering thesis, not a blog post
- Produce the complete .tex file from \documentclass to \end{document} with no sections left empty