# -*- coding: utf-8 -*-
"""Upload a finished set to App Store Connect.

  py -3 scripts/upload-asc.py <bundle-id-or-app-id> <frame-dir> [--display APP_IPHONE_67]

Needs, in the environment or ~/.claude/.env.local:
  APPLE_KEY_ID  APPLE_ISSUER_ID  APPLE_P8_PATH

The three-step reserve -> PUT -> finalise dance has three ways to fail quietly
(references/traps.md #11), and this handles all three:

  1. Sending your bearer token to the pre-signed upload URL returns a bare 400
     with no explanation. Send ONLY the headers Apple hands back in
     `op.requestHeaders`.
  2. A request body with no Content-Type gets labelled as form data by most
     HTTP clients. Apple stores it, cannot decode it, and the asset lands FAILED
     at 0x0. Set image/png explicitly.
  3. If reserve succeeded and the PUT failed, an asset record exists with no
     bytes behind it, and every retry is refused with "Screenshot already
     exists". Existing assets must be DELETED before reserving.

Requires: py -3 -m pip install pyjwt cryptography
"""
import os
import sys
import json
import time
import hashlib
import pathlib
import urllib.request
import urllib.error

try:
    import jwt
except ImportError:
    raise SystemExit("  needs pyjwt:  py -3 -m pip install pyjwt cryptography")

BASE = "https://api.appstoreconnect.apple.com"


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    p = pathlib.Path.home() / ".claude" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(f"  missing {name}")


def token():
    key = pathlib.Path(env("APPLE_P8_PATH")).read_text(encoding="utf-8")
    now = int(time.time())
    return jwt.encode(
        {"iss": env("APPLE_ISSUER_ID"), "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"},
        key,
        algorithm="ES256",
        headers={"kid": env("APPLE_KEY_ID"), "typ": "JWT"},
    )


TOK = token()


def api(path, method="GET", body=None, raw=None, headers=None):
    url = path if path.startswith("http") else BASE + path
    h = dict(headers or {}) if raw is not None else {"Authorization": "Bearer " + TOK}
    data = raw
    if raw is None and body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            b = r.read()
            return r.status, (json.loads(b) if b[:1] in (b"{", b"[") else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


if len(sys.argv) < 3:
    print("usage: py -3 upload-asc.py <bundle-id-or-app-id> <frame-dir> [--display TYPE]")
    raise SystemExit(1)

ident, frame_dir = sys.argv[1], pathlib.Path(sys.argv[2])
display = sys.argv[sys.argv.index("--display") + 1] if "--display" in sys.argv else "APP_IPHONE_67"

# ---- locate the app, the editable version, and its English localization ----
code, apps = api("/v1/apps?limit=100")
if code != 200:
    raise SystemExit(f"  cannot list apps: {code} {apps}")
app = next(
    (a for a in apps["data"] if ident in (a["id"], a["attributes"].get("bundleId"))),
    None,
)
if not app:
    raise SystemExit(f"  no app matching {ident}")
print(f"  app: {app['attributes']['name']}  ({app['attributes']['bundleId']})")

code, vers = api(f"/v1/apps/{app['id']}/appStoreVersions?limit=10")
editable = next(
    (v for v in vers.get("data", [])
     if v["attributes"].get("appStoreState") in
     ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED")),
    None,
)
if not editable:
    raise SystemExit("  no editable version — create one in App Store Connect first")
print(f"  version {editable['attributes'].get('versionString')} ({editable['attributes'].get('appStoreState')})")

code, locs = api(f"/v1/appStoreVersions/{editable['id']}/appStoreVersionLocalizations?limit=20")
loc = next((l for l in locs["data"] if l["attributes"].get("locale", "").startswith("en")), locs["data"][0])
print(f"  locale: {loc['attributes'].get('locale')}")

# ---- find or create the screenshot set ------------------------------------
code, sets = api(f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets?limit=20")
shot_set = next((s for s in sets.get("data", []) if s["attributes"].get("screenshotDisplayType") == display), None)
if not shot_set:
    code, res = api("/v1/appScreenshotSets", "POST", {
        "data": {"type": "appScreenshotSets",
                 "attributes": {"screenshotDisplayType": display},
                 "relationships": {"appStoreVersionLocalization":
                                   {"data": {"type": "appStoreVersionLocalizations", "id": loc["id"]}}}}})
    if code not in (200, 201):
        raise SystemExit(f"  cannot create {display} set: {code} {res}")
    shot_set = res["data"]
    print(f"  created {display} set")
else:
    print(f"  found {display} set")

# TRAP #11c: an orphaned stub refuses every retry with "Screenshot already
# exists", so clear the set before reserving anything.
code, existing = api(f"/v1/appScreenshotSets/{shot_set['id']}/appScreenshots?limit=20")
for old in existing.get("data", []):
    api(f"/v1/appScreenshots/{old['id']}", "DELETE")
if existing.get("data"):
    print(f"  cleared {len(existing['data'])} existing screenshot(s)")

# ---- upload ---------------------------------------------------------------
frames = sorted(
    p for p in frame_dir.glob("*.png")
    if "-raw" not in p.stem and "-at" not in p.stem and p.stem != "set-all"
)
if not frames:
    raise SystemExit(f"  no finished frames in {frame_dir}")
print(f"\n  uploading {len(frames)} frame(s)\n")

for i, p in enumerate(frames, 1):
    blob = p.read_bytes()
    code, res = api("/v1/appScreenshots", "POST", {
        "data": {"type": "appScreenshots",
                 "attributes": {"fileSize": len(blob), "fileName": p.name},
                 "relationships": {"appScreenshotSet":
                                   {"data": {"type": "appScreenshotSets", "id": shot_set["id"]}}}}})
    if code not in (200, 201):
        print(f"  {i}. {p.name}: reserve FAILED {code} {res}")
        continue

    asset = res["data"]
    ok = True
    for op in asset["attributes"]["uploadOperations"]:
        chunk = blob[op["offset"]: op["offset"] + op["length"]]
        # TRAP #11a: ONLY Apple's headers. Adding our bearer token gets a bare 400.
        hdrs = {h["name"]: h["value"] for h in (op.get("requestHeaders") or [])}
        # TRAP #11b: a typeless body is stored as form data and lands FAILED at 0x0.
        hdrs.setdefault("Content-Type", "image/png")
        c, b = api(op["url"], op["method"], raw=chunk, headers=hdrs)
        if c not in (200, 201, 204):
            print(f"  {i}. {p.name}: PUT FAILED {c} {str(b)[:120]}")
            ok = False
            break
    if not ok:
        continue

    code, res = api(f"/v1/appScreenshots/{asset['id']}", "PATCH", {
        "data": {"type": "appScreenshots", "id": asset["id"],
                 "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(blob).hexdigest()}}})
    if code != 200:
        print(f"  {i}. {p.name}: finalise FAILED {code} {res}")
        continue
    print(f"  {i}. {p.name}: uploaded ({len(blob)//1024}KB)")

# ---- confirm Apple actually accepted the pixels ---------------------------
print("\n  waiting for asset processing…")
for _ in range(12):
    time.sleep(6)
    code, shots = api(f"/v1/appScreenshotSets/{shot_set['id']}/appScreenshots?limit=20")
    states = [s["attributes"].get("assetDeliveryState", {}) for s in shots.get("data", [])]
    if all(s.get("state") != "AWAITING_UPLOAD" for s in states) and states:
        break

bad = 0
for s in shots.get("data", []):
    a = s["attributes"]
    st = a.get("assetDeliveryState", {})
    img = a.get("imageAsset") or {}
    flag = ""
    if st.get("state") != "COMPLETE":
        bad += 1
        flag = f"  <-- {st.get('errors') or st.get('warnings')}"
    print(f"  {a.get('fileName'):22} {st.get('state'):12} {img.get('width')}x{img.get('height')}{flag}")

print(f"\n  {'ALL COMPLETE' if not bad else str(bad) + ' FAILED'}")
if bad:
    print("  IMAGE_INCORRECT_DIMENSIONS = the pixels are not a real device size.")
    print("  FAILED at 0x0             = the bytes arrived undecodable (Content-Type).")
    raise SystemExit(1)
