// label-composite: prints a product label onto an AI master photo, so a whole catalog matches.
// See rules/web-design-lessons.md ("Product photos: one master, labels printed by code").
//
// The master's label area must be a flat solid magenta (#FF00FF) placeholder:
//   kit  = a flat sticker seen in perspective  -> homography warp onto its 4 corners
//   vial = a band wrapped round a cylinder     -> cylindrical warp with edge shading
// Then the magenta halo the image model leaves round the object is neutralised.
// Labels are drawn as HTML and screenshotted with a transparent background first.
//
// Usage: SHARP=<any project's node_modules/sharp> node label-composite.cjs <kit|vial> <master.png> <label.png> <out.png>
// First used on example.com, 27 Oct 2026 (24 kits and vials from 2 masters, 0 extra credits).
const sharp = require(process.env.SHARP || "sharp");
const [kind, masterFile, labelFile, outFile] = process.argv.slice(2);

const isMagenta = (r, g, b, a) => a >= 40 && r - g > 70 && b - g > 70 && r > 120 && b > 120;

function largestComponent(mask, W, H) {
  const seen = new Uint8Array(W * H); let best = [];
  for (let s = 0; s < W * H; s++) {
    if (!mask[s] || seen[s]) continue;
    const comp = [], st = [s]; seen[s] = 1;
    while (st.length) {
      const p = st.pop(); comp.push(p); const x = p % W, y = (p / W) | 0;
      if (x > 0 && mask[p - 1] && !seen[p - 1]) { seen[p - 1] = 1; st.push(p - 1); }
      if (x < W - 1 && mask[p + 1] && !seen[p + 1]) { seen[p + 1] = 1; st.push(p + 1); }
      if (y > 0 && mask[p - W] && !seen[p - W]) { seen[p - W] = 1; st.push(p - W); }
      if (y < H - 1 && mask[p + W] && !seen[p + W]) { seen[p + W] = 1; st.push(p + W); }
    }
    if (comp.length > best.length) best = comp;
  }
  const m = new Uint8Array(W * H); for (const p of best) m[p] = 1; return m;
}

function sample(L, LW, LH, x, y) { // bilinear, returns [r,g,b,a]
  x = Math.max(0, Math.min(LW - 1.001, x)); y = Math.max(0, Math.min(LH - 1.001, y));
  const x0 = x | 0, y0 = y | 0, fx = x - x0, fy = y - y0, o = [0, 0, 0, 0];
  for (let k = 0; k < 4; k++) {
    const a = L[(y0 * LW + x0) * 4 + k], b = L[(y0 * LW + x0 + 1) * 4 + k];
    const c = L[((y0 + 1) * LW + x0) * 4 + k], d = L[((y0 + 1) * LW + x0 + 1) * 4 + k];
    o[k] = (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
  }
  return o;
}

// Solves the 3x3 homography taking 4 source points to 4 destination points.
function homography(src, dst) {
  const A = [], B = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, v] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); B.push(v);
  }
  for (let c = 0; c < 8; c++) {
    let p = c; for (let r = c + 1; r < 8; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
    [A[c], A[p]] = [A[p], A[c]]; [B[c], B[p]] = [B[p], B[c]];
    for (let r = 0; r < 8; r++) { if (r === c) continue; const f = A[r][c] / A[c][c]; for (let k = c; k < 8; k++) A[r][k] -= f * A[c][k]; B[r] -= f * B[c]; }
  }
  const h = B.map((b, i) => b / A[i][i]); return [...h, 1];
}
const apply = (h, x, y) => { const w = h[6] * x + h[7] * y + h[8]; return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w]; };

(async () => {
  const { data: M, info } = await sharp(masterFile).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const W = info.width, H = info.height;
  const { data: L, info: li } = await sharp(labelFile).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const LW = li.width, LH = li.height;
  const raw = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) raw[i] = isMagenta(M[i * 4], M[i * 4 + 1], M[i * 4 + 2], M[i * 4 + 3]) ? 1 : 0;
  const mask = largestComponent(raw, W, H);
  const covered = new Uint8Array(W * H);

  if (kind === "kit") {
    let tl = [0, 0, 1e9], br = [0, 0, -1e9], tr = [0, 0, -1e9], bl = [0, 0, 1e9];
    for (let p = 0; p < W * H; p++) if (mask[p]) { const x = p % W, y = (p / W) | 0;
      if (x + y < tl[2]) tl = [x, y, x + y]; if (x + y > br[2]) br = [x, y, x + y];
      if (x - y > tr[2]) tr = [x, y, x - y]; if (x - y < bl[2]) bl = [x, y, x - y]; }
    const quad = [tl, tr, br, bl].map((q) => q.slice(0, 2));
    const cx = quad.reduce((a, q) => a + q[0], 0) / 4, cy = quad.reduce((a, q) => a + q[1], 0) / 4;
    // Rounded corners put the extreme points inside the true corners; grow the quad a little.
    const grown = quad.map(([x, y]) => { const dx = x - cx, dy = y - cy, d = Math.hypot(dx, dy); return [x + (dx / d) * 14, y + (dy / d) * 14]; });
    const inv = homography(grown, [[0, 0], [LW, 0], [LW, LH], [0, LH]]);
    const xs = grown.map((q) => q[0]), ys = grown.map((q) => q[1]);
    for (let y = Math.floor(Math.min(...ys)); y <= Math.ceil(Math.max(...ys)); y++) {
      for (let x = Math.floor(Math.min(...xs)); x <= Math.ceil(Math.max(...xs)); x++) {
        if (x < 0 || y < 0 || x >= W || y >= H) continue;
        const [u, v] = apply(inv, x + 0.5, y + 0.5);
        if (u < 0 || v < 0 || u > LW || v > LH) continue;
        const s = sample(L, LW, LH, u, v); const la = s[3] / 255; if (la <= 0) continue;
        const nu = u / LW, nv = v / LH;
        const shade = 1.04 - 0.1 * nv - 0.05 * nu; // light from the top left
        const sheen = 22 * Math.exp(-(((nu - nv * 0.55) - 0.18) ** 2) / 0.006); // gloss on the lid
        const i = (y * W + x) * 4;
        for (let k = 0; k < 3; k++) M[i + k] = Math.min(255, (s[k] * shade + sheen) * la + M[i + k] * (1 - la));
        M[i + 3] = Math.round(255 * la + M[i + 3] * (1 - la));
        if (la > 0.5) covered[y * W + x] = 1;
      }
    }
  } else {
    let x0 = W, x1 = 0; const top = new Int32Array(W).fill(-1), bot = new Int32Array(W).fill(-1);
    for (let p = 0; p < W * H; p++) if (mask[p]) { const x = p % W, y = (p / W) | 0; x0 = Math.min(x0, x); x1 = Math.max(x1, x);
      if (top[x] < 0 || y < top[x]) top[x] = y; if (y > bot[x]) bot[x] = y; }
    const cx = (x0 + x1) / 2, R = (x1 - x0) / 2 + 2;
    for (let x = x0 - 2; x <= x1 + 2; x++) {
      const tx = top[Math.min(x1, Math.max(x0, x))], bx = bot[Math.min(x1, Math.max(x0, x))];
      const uu = Math.max(-1, Math.min(1, (x + 0.5 - cx) / R)), th = Math.asin(uu);
      const t = 0.5 + th / Math.PI; // the visible half of the wrap
      const shade = 0.64 + 0.36 * Math.pow(Math.cos(th), 0.55);
      const spec = 46 * Math.exp(-(((th + 0.5) / 0.16) ** 2)) + 14 * Math.exp(-(((th - 0.9) / 0.1) ** 2));
      for (let y = tx - 1; y <= bx + 1; y++) {
        const v = (y + 0.5 - tx) / Math.max(1, bx - tx);
        if (v < -0.004 || v > 1.004) continue;
        const s = sample(L, LW, LH, t * LW, Math.max(0, Math.min(1, v)) * LH);
        const i = (y * W + x) * 4;
        for (let k = 0; k < 3; k++) M[i + k] = Math.min(255, s[k] * shade + spec);
        M[i + 3] = 255; covered[y * W + x] = 1;
      }
    }
  }

  for (let p = 0; p < W * H; p++) { // neutralise the magenta glow left round the object
    if (covered[p]) continue;
    const i = p * 4, r = M[i], g = M[i + 1], b = M[i + 2];
    const m = Math.min(r, b) - g;
    if (m <= 18) continue;
    const lum = 0.3 * r + 0.59 * g + 0.11 * b;
    const k = Math.min(1, (m - 18) / 90);
    M[i] = lum * 0.93; M[i + 1] = lum * 0.98; M[i + 2] = Math.min(255, lum * 1.06);
    M[i + 3] = Math.round(M[i + 3] * (1 - 0.75 * k));
  }
  await sharp(M, { raw: { width: W, height: H, channels: 4 } }).png().toFile(outFile);
  console.log("wrote", outFile);
})();
