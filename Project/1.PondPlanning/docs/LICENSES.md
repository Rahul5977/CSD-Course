# Data-source and dependency licence register

| Source | Used for | Licence / terms | Attribution string |
|---|---|---|---|
| Provided sample contour map (`data/samples/contours_1m.kml`) | Development and the demonstration | Course material | "ContourMapGenerator" output; its own `sources` placemark attributes the terrain to Mapzen terrain tiles / SRTM |
| NASA/USGS SRTM v3 (via the sample's provenance) | Source DEM accuracy figures | Public domain | SRTM terrain data courtesy of NASA and the U.S. Geological Survey |
| USGS GMTED2010, HydroSHEDS © WWF, Mapzen terrain tiles | Named in the sample's provenance | GMTED public domain; HydroSHEDS licence (WWF); Mapzen (CC BY 4.0) | As listed in the sample's `sources` placemark |
| Esri World Imagery | Satellite basemap (FR1) | Esri master agreement, non-commercial/educational display | "Esri, Maxar, Earthstar Geographics, and the GIS User Community" |
| Open-Meteo archive (ERA5-Land) | Daily rainfall 1981–2025 | CC BY 4.0 (Open-Meteo); ERA5-Land © ECMWF / Copernicus C3S | "Open-Meteo.com; ERA5-Land © ECMWF / Copernicus C3S" |
| NASA POWER (MERRA-2) | Rainfall fallback | Public domain | "NASA POWER Project, Langley Research Center" |
| ESA WorldCover 2021 v200 | Land cover for the curve number and land constraints | CC BY 4.0 | "© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)" |
| ISRIC SoilGrids v2.0 | Topsoil texture → hydrologic soil group | CC BY 4.0 | "ISRIC — World Soil Information, SoilGrids 2.0" |
| Copernicus Sentinel-2 L2A (Earth Search STAC, AWS open data) | NDWI water mask | Free and open (Copernicus Sentinel data terms) | "Contains modified Copernicus Sentinel data 2025" |
| OpenStreetMap / Nominatim | Village name from the AOI centroid; existing tanks for the reality check | ODbL 1.0; Nominatim usage policy (1 req/s, identified User-Agent) | "© OpenStreetMap contributors" |
| MapLibre demo tiles glyphs | Contour label fonts | MapLibre demo, not for production | Replace with self-hosted glyphs in production |

## Software

Python: FastAPI, Pydantic, SQLAlchemy/GeoAlchemy2, Alembic, Celery, redis-py, MinIO SDK,
numpy, scipy, shapely, pyproj, rasterio (GDAL), lxml, contourpy, opencv-python-headless,
PyJWT + cryptography, prometheus-client, reportlab (all MIT/BSD/Apache-2.0 family; GDAL MIT;
OpenCV Apache-2.0; reportlab BSD). Dev: ruff, mypy, pytest, pysheds (GPL-3.0 — dev/validation
only, never shipped in the image), locust (MIT), matplotlib (PSF).
JavaScript: React, Vite, MapLibre GL JS (BSD-3), openapi-typescript (MIT).
Containers: PostGIS, Redis, MinIO (AGPL-3.0 — run unmodified as a service), TiTiler (MIT),
Prometheus and Grafana (Apache-2.0 / AGPL-3.0 — run unmodified), nginx (BSD-2).
