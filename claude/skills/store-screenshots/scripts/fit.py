# -*- coding: utf-8 -*-
"""Centre-crop a generated plate to the store frame ratio and downsample it.

  py -3 scripts/fit.py <in.jpg> <out.jpg> <width> <height>
  py -3 scripts/fit.py art/f1-s11.jpg art/f1-bg.jpg 1320 2868

Store frames are taller than any image model's maximum aspect ratio, so the
plate always arrives wider than it needs to be. Crop the excess from the sides,
keep the centre, then resize DOWN with Lanczos.

The one rule: never upscale. If the source is smaller than the target in either
axis this refuses, because a stretched plate is visible and there is no fixing
it later.
"""
import sys
import pathlib
from PIL import Image

if len(sys.argv) < 5:
    print("usage: py -3 fit.py <in> <out> <width> <height>")
    raise SystemExit(1)

src, dst, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])

im = Image.open(src).convert("RGB")
sw, sh = im.size
if sw < W or sh < H:
    raise SystemExit(
        f"  REFUSING: source {sw}x{sh} is smaller than target {W}x{H} in at least one axis.\n"
        f"  Generate at a higher resolution rather than upscaling."
    )

target = W / H
if sw / sh > target:
    new_w = round(sh * target)
    left = (sw - new_w) // 2
    im = im.crop((left, 0, left + new_w, sh))
else:
    new_h = round(sw / target)
    top = (sh - new_h) // 2
    im = im.crop((0, top, sw, top + new_h))

factor = im.size[0] / W
print(f"  cropped {sw}x{sh} -> {im.size[0]}x{im.size[1]}, downsampling {factor:.2f}x")

im = im.resize((W, H), Image.LANCZOS)
pathlib.Path(dst).parent.mkdir(parents=True, exist_ok=True)
im.save(dst, quality=96, subsampling=0)
print(f"  wrote {dst}  {im.size[0]}x{im.size[1]}")
