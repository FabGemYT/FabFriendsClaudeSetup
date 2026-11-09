# -*- coding: utf-8 -*-
"""Make a rendered frame submittable, and prove it reads at listing size.

  py -3 scripts/finish.py <name> [width] [height] [--dir out]
  py -3 scripts/finish.py f1 1320 2868

Two jobs.

FLATTEN. Every headless browser writes RGBA and both stores reject alpha, so
this is not optional (references/traps.md #7). The frame looks identical either
way, which is exactly why it gets missed.

PROVE IT READS. A store search result shows a screenshot about 175px wide and
the product page about 300px. A headline that dissolves at 175px is the wrong
TYPEFACE, not the wrong size — no amount of scaling fixes a hairline serif.
Look at the -at175 file before showing anyone the full-size version.
"""
import sys
import pathlib
from PIL import Image

args = [a for a in sys.argv[1:] if not a.startswith("--")]
name = args[0] if args else None
W = int(args[1]) if len(args) > 1 else 1320
H = int(args[2]) if len(args) > 2 else 2868
OUT = pathlib.Path(sys.argv[sys.argv.index("--dir") + 1] if "--dir" in sys.argv else "out")

if not name:
    print("usage: py -3 finish.py <name> [width] [height] [--dir out]")
    raise SystemExit(1)

src = OUT / f"{name}-raw.png"
if not src.exists():
    raise SystemExit(f"  no {src} — run render.mjs first")

im = Image.open(src)
if im.size != (W, H):
    raise SystemExit(f"  WRONG SIZE {im.size}, expected {W}x{H} — the store will reject this")

flat = Image.new("RGB", im.size, (0, 0, 0))
flat.paste(im, mask=im.split()[3] if im.mode == "RGBA" else None)

dst = OUT / f"{name}.png"
flat.save(dst, optimize=True)
kb = dst.stat().st_size // 1024
print(f"  {dst.name}: {flat.size[0]}x{flat.size[1]} {flat.mode}  {kb}KB")
if kb > 5000:
    print(f"  WARN  {kb}KB is large for a store asset; consider JPEG or more compression")

# Legibility proofs. The x4 nearest-neighbour blow-up is so a human can see what
# actually survives at listing size rather than squinting at a 175px file.
for w, label in ((175, "store search result"), (300, "product page")):
    t = flat.resize((w, round(H * w / W)), Image.LANCZOS)
    t.save(OUT / f"{name}-at{w}.png")
    t.resize((w * 4, t.size[1] * 4), Image.NEAREST).save(OUT / f"{name}-at{w}-x4.png")
    print(f"  {name}-at{w}.png  ({label})  + -x4 for inspection")

print("""
  Look at the -at175-x4 file. If the headline is mush there, change the
  TYPEFACE, not the size.
""")
