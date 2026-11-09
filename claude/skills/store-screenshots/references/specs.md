# Store specs

Every number here was verified against a live source, not read off a docs page.
Docs pages get summarised wrong: on one check, Apple's own help page was read
back as `1260 × 2736` for the 6.9" slot, which would have produced a rejected
upload. The live apps say otherwise.

## App Store

| | |
|---|---|
| Portrait phone, 6.9" | **1320 × 2868** (also accepted: 1290 × 2796) |
| Display type in the API | `APP_IPHONE_67` |
| Count | **1–10** per localization |
| Format | `.png`, `.jpg`, `.jpeg` |
| Alpha | **not allowed** — "Images can't include alpha channels or transparencies" |
| Smaller devices | 6.9" screenshots are **auto-scaled down**; you do not need the other sizes |

### How to re-verify, in 30 seconds

Do not trust this file. Ask the API what shipping apps actually have:

```
GET /v1/apps?limit=30
GET /v1/apps/{id}/appStoreVersions?limit=3
GET /v1/appStoreVersions/{id}/appStoreVersionLocalizations?limit=3
GET /v1/appStoreVersionLocalizations/{id}/appScreenshotSets?limit=20
GET /v1/appScreenshotSets/{id}/appScreenshots?limit=20
```

Each screenshot carries `attributes.imageAsset.width/height` and the set carries
`screenshotDisplayType`. Whatever is sitting in an approved listing is, by
definition, accepted.

## Google Play

| | |
|---|---|
| Phone screenshot, min dimension | **320 px** |
| Phone screenshot, max dimension | **3840 px** |
| Ratio constraint | max dimension **cannot exceed 2×** the min dimension |
| Recommended portrait | 9:16, at least **1080 × 1920** |
| Count | **2–8** per device type, minimum 2 across device types |
| Format | JPEG or **24-bit PNG (no alpha)** |
| Feature graphic | **1024 × 500**, JPEG or 24-bit PNG, no alpha |
| App icon | **512 × 512**, 32-bit PNG **with** alpha, max 1024 KB |

Note the icon is the one asset that *wants* alpha. Everything else must be flat.

A 1320 × 2868 App Store frame satisfies Play's phone rules as-is (2868 < 2×1320
is false — 2868 > 2640 — so **crop or pad to 1320 × 2640 or wider before
uploading to Play**). Check this per-frame; it is the single easiest way to get
a Play asset rejected after an App Store set sailed through.

## Colour space and file size

Neither store publishes a hard file-size cap for phone screenshots in practice,
but keep frames under ~5 MB. sRGB. Optimised PNG from `finish.py` typically
lands at 1.7–2.3 MB for a 1320 × 2868 frame with photographic art.

## The upload path (App Store Connect)

Three steps, and each one has a way to fail quietly. See `traps.md` #11.

1. **Reserve** — `POST /v1/appScreenshots` with `fileSize` and `fileName`, plus a
   relationship to the screenshot set. Returns `uploadOperations`.
2. **PUT** — send each chunk to `op.url` with **only** the headers in
   `op.requestHeaders`. Sending your bearer token here gets a bare 400.
3. **Finalise** — `PATCH /v1/appScreenshots/{id}` with `uploaded: true` and
   `sourceFileChecksum` set to the MD5 of the whole file.

Then poll `assetDeliveryState.state`. `FAILED` with `IMAGE_INCORRECT_DIMENSIONS`
means the pixels are not a real device size. `FAILED` at 0×0 means the bytes
arrived undecodable, which is almost always a missing `Content-Type`.
