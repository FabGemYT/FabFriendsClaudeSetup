// canvas-preview: renders a Design-canvas artboard (.dc.html) locally with the canvas's own runtime
// and screenshots it, so a mockup is checked on laptop and phone sizes before the owner sees it.
// See rules/web-design-lessons.md ("Mockups on a Design canvas, verified locally").
//
// Usage:
//   node canvas-preview.cjs --project <dir with .dc.html files> --name <Artboard> \
//     --runtime <dc-runtime.js> [--blobs <ids.json> --web <dir of local images>] [--out <dir>] \
//     1280x600 p390x700 ...
// --runtime: the type's artifact-type/dc-runtime.js (Artifact read on the canvas with `path`).
// --blobs:   {"<32-hex id>": "file.webp"} so /_blob/<id> loads the local copy from --web.
// "p390x700" is a phone: headless Chrome won't make a window narrower than about 500px, so the
// page loads inside an exact-width iframe and the shot is cropped to it (needs SHARP=<sharp path>).
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
const sizes = args.filter((a, i) => /^p?\d+x\d+$/.test(a) && !String(args[i - 1] || "").startsWith("--"));
const project = opt("--project"), name = opt("--name"), runtime = opt("--runtime");
if (!project || !name || !runtime || !sizes.length) { console.error("see the usage at the top of this file"); process.exit(1); }
const out = opt("--out") || path.join(project, "..", "_preview");

let src = fs.readFileSync(path.join(project, name + ".dc.html"), "utf8");
if (opt("--blobs")) {
  const blobs = JSON.parse(fs.readFileSync(opt("--blobs"), "utf8"));
  const web = "file:///" + path.resolve(opt("--web") || ".").replace(/\\/g, "/") + "/";
  for (const [id, f] of Object.entries(blobs)) src = src.split("/_blob/" + id).join(web + f);
}
fs.mkdirSync(out, { recursive: true });
fs.copyFileSync(runtime, path.join(out, "support.js"));
const file = path.join(out, name + ".html");
fs.writeFileSync(file, src);

(async () => {
  for (const s of sizes) {
    const phone = s.startsWith("p");
    const [w, h] = s.replace(/^p/, "").split("x").map(Number);
    const png = path.join(out, `${name}-${s}.png`);
    let target = file, win = w;
    if (phone) {
      target = path.join(out, `${name}-frame-${w}.html`);
      fs.writeFileSync(target, `<!doctype html><html><body style="margin:0;background:#888"><iframe src="${name}.html" style="border:0;width:${w}px;height:${h}px;display:block"></iframe></body></html>`);
      win = Math.max(600, w + 20);
    }
    execFileSync(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1", "--allow-file-access-from-files",
      `--window-size=${win},${h}`, "--virtual-time-budget=9000", `--screenshot=${png}`, "file:///" + target.replace(/\\/g, "/")], { stdio: "ignore" });
    if (phone) {
      const sharp = require(process.env.SHARP || "sharp");
      fs.writeFileSync(png, await sharp(png).extract({ left: 0, top: 0, width: w, height: h }).toBuffer());
    }
    console.log(png);
  }
})();
