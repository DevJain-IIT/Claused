"""Crop figure regions from rendered pages."""
from PIL import Image
from pathlib import Path

ROOT = Path(__file__).parent
PAGES = ROOT / "pages"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# Coordinates determined by visual inspection of the rendered pages (709×1006 px)
# Fig 1 — entire page 18 (page is essentially just the figure + caption)
Image.open(PAGES / "p_18.png").save(DATA / "fig1_phi_vs_N.png")

# Fig 2 — top half of page 19, includes the chart and "Fig. 2" caption
Image.open(PAGES / "p_19.png").crop((40, 60, 700, 540)).save(DATA / "fig2_cone_test_chart.png")

# Fig 3 — bottom 2/3 of page 20: the chart only (skip the small soil-layer inset)
Image.open(PAGES / "p_20.png").crop((40, 380, 700, 990)).save(DATA / "fig3_layered_cohesive.png")

# Fig 4 — top of page 21
Image.open(PAGES / "p_21.png").crop((40, 60, 700, 470)).save(DATA / "fig4_desiccated.png")

for f in sorted(DATA.glob("fig*.png")):
    img = Image.open(f)
    print(f"  {f.name}: {img.size}")
