# ADR 0012 — Store ownership class, never owner names; harden every upload

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

FR3 identifies land available for excavation, which in practice means reading
cadastral parcel data. Real cadastral records carry owner names, parent names and
sometimes Aadhaar-linked identifiers. Separately, two routes accept file uploads
(contour maps, parcel imports), and file upload is the most reliably exploited
surface in a web application.

## Decision — data

Parcels are stored with an `ownership_class` of `government`, `community`,
`private` or `unknown`. **Owner names are never stored, logged, or returned.**

Under the Digital Personal Data Protection Act 2023, an owner's name tied to a
plot is personal data, and storing it would pull this project into consent,
purpose-limitation and erasure obligations that a student prototype cannot
discharge. The suitability decision needs to know whether land is government or
community held; it never needs to know whose it is.

## Decision — uploads

Every upload route applies, before parsing:

1. **Size cap** from configuration (`POND_MAX_UPLOAD_MB`, default 64).
2. **Extension and content-type whitelist** — `.kml`, `.kmz`, `.geojson`, `.zip`.
3. **Archive-entry validation** for KMZ and zipped Shapefiles: reject absolute
   paths, `..` traversal, symlinks, and entries whose uncompressed size exceeds a
   ratio bound (zip bombs).
4. **Driver whitelist** on the geospatial reader, so a crafted file cannot reach
   a parser we did not intend to run.
5. **Parse to a temporary path that is always deleted**, never to a
   web-reachable location.

## Consequences

The API can never leak an owner's identity, because it does not hold one — which
is a stronger guarantee than access control, and a short answer to the obvious
viva question about privacy. Item 1 also happens to protect the worker pool: a
200 MB KML is rejected at the boundary rather than after it has consumed a
worker's memory.
