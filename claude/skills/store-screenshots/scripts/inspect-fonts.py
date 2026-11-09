# -*- coding: utf-8 -*-
"""What is actually inside a font file someone handed you?

  py -3 scripts/inspect-fonts.py <dir-or-file> ["the exact string you will set"]

Files named DEMO, FREE or TRIAL are routinely cut down: missing lowercase,
missing punctuation, or licensed for personal use only. One real case (see
references/traps.md #9) was a file called "Vanguard FREE.otf" that turned out to
be by a completely different foundry and held 56 glyphs with no period, no
comma and no digits — it could not set a headline containing a full stop, and
its fsType forbade webfont embedding anyway.

Reports, per file:
  - family / subfamily / full name  (a file that calls itself DEMO will say so)
  - glyph count and cmap size
  - fsType embedding permission
  - which of YOUR characters are missing
  - trademark, licence, licence URL, manufacturer, designer

Requires: py -3 -m pip install fonttools brotli
"""
import sys
import pathlib

try:
    from fontTools.ttLib import TTFont
except ImportError:
    raise SystemExit("  needs fonttools:  py -3 -m pip install fonttools brotli")

FSTYPE = {
    0: "Installable — embedding unrestricted",
    2: "RESTRICTED — must not be embedded",
    4: "Preview & Print only — webfont embedding NOT permitted",
    8: "Editable embedding permitted",
}

target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
NEEDED = sys.argv[2] if len(sys.argv) > 2 else (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'’\"!?;:()-—–&%"
)

files = [target] if target.is_file() else sorted(
    p for p in target.rglob("*") if p.suffix.lower() in (".otf", ".ttf", ".woff", ".woff2")
)
if not files:
    raise SystemExit(f"  no font files under {target}")

for p in files:
    try:
        f = TTFont(str(p), fontNumber=0, lazy=True)
    except Exception as e:
        print(f"\n  {p.name}: UNREADABLE — {e}")
        continue

    names = {}
    for r in f["name"].names:
        try:
            names.setdefault(r.nameID, r.toUnicode())
        except Exception:
            pass

    cmap = set()
    for t in f["cmap"].tables:
        cmap |= set(t.cmap.keys())
    missing = [c for c in NEEDED if ord(c) not in cmap]

    fstype = getattr(f["OS/2"], "fsType", None)
    perm = FSTYPE.get(fstype & 0x0F if isinstance(fstype, int) else -1, f"raw {fstype}")
    extra = []
    if isinstance(fstype, int):
        if fstype & 0x0100:
            extra.append("no subsetting")
        if fstype & 0x0200:
            extra.append("bitmap embedding only")

    full = names.get(4) or ""
    warn = "  <-- DEMO/TRIAL, not licensed for production" if any(
        w in full.upper() for w in ("DEMO", "TRIAL", "FREE")
    ) else ""

    print(f"\n  {p.name}{warn}")
    print(f"     family    : {names.get(16) or names.get(1)}   subfamily: {names.get(17) or names.get(2)}")
    print(f"     full name : {full}")
    print(f"     glyphs    : {len(f.getGlyphOrder())}   cmap: {len(cmap)}")
    print(f"     fsType    : {fstype} — {perm}{(' + ' + ', '.join(extra)) if extra else ''}")
    if missing:
        print(f"     MISSING   : {''.join(missing)!r}")
        print(f"                 CANNOT set your copy with this file.")
    else:
        print(f"     coverage  : complete for the string you gave")
    for nid, label in ((7, "trademark"), (8, "manufacturer"), (9, "designer"), (13, "licence"), (14, "licence url")):
        v = names.get(nid)
        if v:
            print(f"     {label:12}: {v.strip()[:140]}")
    f.close()

print("""
  fsType is the foundry's embedded HINT, not the licence you bought. It is a
  reliable signal that a file was never meant for the web, and no substitute for
  reading the actual licence.
""")
