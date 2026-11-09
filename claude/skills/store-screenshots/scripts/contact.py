# -*- coding: utf-8 -*-
"""Contact sheet of a finished set, and the final submittability gate.

  py -3 scripts/contact.py <out-dir> [width] [height] [--captions "a,b,c"]
  py -3 scripts/contact.py out 1320 2868

Two reasons this exists.

One: a set has to work as a SET. Looked at one at a time, seven frames can each
be fine and still not belong together. Side by side, a mismatched exposure or a
headline that sits at a different height jumps out immediately — that is how a
first screenshot that was 30% darker than the other eight got caught.

Two: it is the last chance to catch an alpha channel or an off-by-one
dimension before upload. Both are asserted here and the script exits non-zero
if any frame fails.
"""
import sys
import pathlib
from PIL import Image, ImageDraw

args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = pathlib.Path(args[0] if args else "out")
W = int(args[1]) if len(args) > 1 else 1320
H = int(args[2]) if len(args) > 2 else 2868

captions = []
if "--captions" in sys.argv:
    captions = [c.strip() for c in sys.argv[sys.argv.index("--captions") + 1].split(",")]

frames = sorted(
    p for p in OUT.glob("*.png")
    if "-raw" not in p.stem and "-at" not in p.stem and p.stem != "set-all"
)
if not frames:
    raise SystemExit(f"  no finished frames in {OUT}")

TW = max(200, min(360, 2400 // len(frames)))
TH = round(H * TW / W)
PAD, LAB = 16, 44
sheet = Image.new("RGB", (PAD + (TW + PAD) * len(frames), TH + LAB + PAD), (10, 10, 12))
d = ImageDraw.Draw(sheet)

bad = 0
for i, p in enumerate(frames):
    im = Image.open(p)
    problems = []
    if im.size != (W, H):
        problems.append(f"WRONG SIZE {im.size}")
    if im.mode != "RGB":
        problems.append(f"ALPHA CHANNEL ({im.mode}) — both stores reject this")
    kb = p.stat().st_size // 1024
    cap = captions[i] if i < len(captions) else p.stem

    if problems:
        bad += 1
        print(f"  {i+1}. {p.stem:14} FAIL  {'; '.join(problems)}")
    else:
        print(f"  {i+1}. {p.stem:14} {im.size[0]}x{im.size[1]}  {im.mode}  {kb}KB   {cap}")

    x = PAD + (TW + PAD) * i
    sheet.paste(im.convert("RGB").resize((TW, TH), Image.LANCZOS), (x, LAB))
    d.text((x + 2, 15), f"{i+1}. {cap[:34]}", fill=(219, 171, 124))

sheet.save(OUT / "set-all.png")
print(f"\n  contact sheet -> {OUT / 'set-all.png'}  {sheet.size}")

if bad:
    print(f"  {bad} frame(s) are NOT submittable.")
    raise SystemExit(1)
print(f"  all {len(frames)} verified submittable.")
print("""
  Look at the sheet before you upload. You are checking three things:
    - do all the headlines sit at the same height?
    - is any one frame noticeably darker or brighter than its neighbours?
    - does the set read as one story, or as separate feature demos?
""")
