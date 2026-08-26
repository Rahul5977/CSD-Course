"""NDWI water-mask figure (evidence row 19): raw NDWI → Otsu → OpenCV clean-up.

Fetches the post-monsoon Sentinel-2 composite for the sample's extent live
(needs the network) and writes docs/figures/p4-ndwi-opencv.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cv2  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engines.suitability.water_mask import ndwi, water_mask_from_ndwi  # noqa: E402
from app.providers.contour_kml import parse_contours  # noqa: E402
from app.providers.sentinel import season_composite  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "contours_1m.kml"
OUT = ROOT / "docs" / "figures" / "p4-ndwi-opencv.png"


def main() -> None:
    contours = parse_contours(SAMPLE.read_bytes(), SAMPLE.name)
    bounds = contours.bounds
    year = 2025
    post = season_composite(bounds, f"{year}-10-01", f"{year}-12-31", "post-monsoon")
    index = ndwi(post.green, post.nir)
    result = water_mask_from_ndwi(index, pixel_size_m=abs(post.transform[0]))
    valid = ~np.isnan(index)
    scaled = np.zeros(index.shape, np.uint8)
    scaled[valid] = np.clip((index[valid] + 1) * 127.5, 0, 255).astype(np.uint8)
    _, raw = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if result.otsu_threshold == 0.0:
        raw = ((index > 0) & valid).astype(np.uint8) * 255
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    im = axes[0].imshow(index, cmap="RdYlBu", vmin=-0.6, vmax=0.6)
    axes[0].set_title(f"NDWI (Sentinel-2 post-monsoon median, {len(post.scenes)} scenes)")
    fig.colorbar(im, ax=axes[0])
    axes[1].imshow(raw > 0, cmap="Blues")
    axes[1].set_title(f"Otsu threshold {result.otsu_threshold:.2f} → {result.components_before} components")
    axes[2].imshow(result.mask, cmap="Blues")
    axes[2].set_title(
        f"OpenCV open/close + components ≥ 200 m² → {result.components_after} water bodies "
        f"({result.water_fraction:.1%} of area)"
    )
    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT, dpi=130)
    print("scenes:", post.scenes)
    print(f"otsu {result.otsu_threshold:.3f}; components {result.components_before} -> {result.components_after}; water {result.water_fraction:.1%}")
    print("wrote", OUT.name)


if __name__ == "__main__":
    main()
