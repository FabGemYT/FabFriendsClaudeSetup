#!/usr/bin/env node
/**
 * Installs (or updates) this Claude setup into ~/.claude. Claude runs it; the owner never
 * has to. Safe to run again and again: a second run changes nothing.
 *
 *   node install.mjs                     install or update ~/.claude
 *   node install.mjs --target <dir>      install somewhere else (tests)
 *   node install.mjs --no-tests          skip the safety-guard check at the end
 *   node install.mjs --no-downloads      skip the skills fetched from their own source
 *
 * What it promises:
 *  - The owner's own files are never touched once they exist: about-me.md,
 *    rules/secrets-map.md, .env.local, my-settings.json and everything in secrets/.
 *  - Any other file it is about to replace is backed up first, once, to
 *    backups/setup-<date>/ inside the target. Nothing is ever deleted.
 *  - settings.json = this setup's settings + the owner's my-settings.json, keeping any
 *    setting Claude Code itself saved (a /model or /config choice) that this setup does not manage.
 *  - The safety guards fail CLOSED without Python 3: they would block every command. So when
 *    Python is missing the files are installed but the guards are NOT switched on, and it
 *    says so loudly. Install Python, run this again, and they switch on.
 * Exit codes: 0 installed, 2 usage, 3 installed without the guards (Python missing),
 * 4 installed but a guard test failed.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PAYLOAD = path.join(HERE, "claude");
const args = process.argv.slice(2);
const flag = (f) => args.includes(f);
const targetAt = args.indexOf("--target");
const TARGET = path.resolve(targetAt === -1 ? path.join(os.homedir(), ".claude") : args[targetAt + 1] || "");
if (targetAt !== -1 && !args[targetAt + 1]) { console.error("install: --target needs a folder"); process.exit(2); }
if (!fs.existsSync(path.join(PAYLOAD, "settings.json"))) {
  console.error(`install: ${PAYLOAD} is not this setup's payload (no settings.json). Run it from the cloned folder.`);
  process.exit(2);
}

// Files that belong to the owner: created from a template when missing, never overwritten.
const PERSONAL = {
  "about-me.md": "about-me.example.md",
  "rules/secrets-map.md": "rules/secrets-map.md",
  ".env.local": null,
  "my-settings.json": null,
};
const IS_WIN = process.platform === "win32";
const STAMP = new Date().toISOString().slice(0, 10);
const BACKUP = path.join(TARGET, "backups", `setup-${STAMP}`);
const report = { added: 0, updated: 0, same: 0, backedUp: 0, personalCreated: [] };

const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
const rel = (p) => path.relative(PAYLOAD, p).split(path.sep).join("/");

function walk(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else if (e.isFile()) out.push(p);
  }
  return out;
}

function backup(dest) {
  const b = path.join(BACKUP, path.relative(TARGET, dest));
  if (fs.existsSync(b)) return;                     // the first version of the day is the one kept
  fs.mkdirSync(path.dirname(b), { recursive: true });
  fs.copyFileSync(dest, b);
  report.backedUp += 1;
}

function writeIfChanged(dest, buf, mode) {
  if (fs.existsSync(dest)) {
    const cur = fs.readFileSync(dest);
    if (sha(cur) === sha(buf)) { report.same += 1; return false; }
    backup(dest);
    report.updated += 1;
  } else {
    report.added += 1;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, buf);
  if (mode !== undefined && !IS_WIN) fs.chmodSync(dest, mode);
  return true;
}

function findPython() {
  if (flag("--pretend-no-python")) return null;     // used by the tests
  const tries = IS_WIN ? [["py", ["-3"]], ["python3", []], ["python", []]] : [["python3", []], ["python", []]];
  for (const [cmd, pre] of tries) {
    const r = spawnSync(cmd, [...pre, "-c", "import sys; assert sys.version_info >= (3, 8); print(sys.executable)"],
      { encoding: "utf8", windowsHide: true });
    if (r.status === 0 && r.stdout.trim()) return { cmd, pre, exe: r.stdout.trim() };
  }
  return null;
}

function readJson(p, fallback) {
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return fallback; }
}

const uniq = (xs) => [...new Map(xs.map((x) => [JSON.stringify(x), x])).values()];

function mergeSettings(template, existing, mine, pythonOk) {
  const out = {};
  // 1. Keep what Claude Code saved itself (a /model choice, a theme) when this setup does not manage it.
  for (const [k, v] of Object.entries(existing || {})) if (!(k in template)) out[k] = v;
  // 2. This setup's settings.
  Object.assign(out, structuredClone(template));
  // 3. The owner's own additions win, merged rather than replaced where lists are involved.
  for (const [k, v] of Object.entries(mine || {})) {
    if (k === "permissions" && v && typeof v === "object") continue;
    if (k === "autoMode" && v && typeof v === "object") continue;
    out[k] = v;
  }
  const tp = template.permissions || {}, ep = (existing || {}).permissions || {}, mp = (mine || {}).permissions || {};
  out.permissions = {
    ...tp,
    allow: uniq([...(tp.allow || []), ...(ep.allow || []), ...(mp.allow || [])]),
    deny: uniq([...(tp.deny || []), ...(mp.deny || [])]),
    ask: uniq([...(tp.ask || []), ...(mp.ask || [])]),
    ...(mp.defaultMode ? { defaultMode: mp.defaultMode } : {}),
  };
  const tenv = ((template.autoMode || {}).environment) || [];
  const menv = (((mine || {}).autoMode || {}).environment) || [];
  out.autoMode = { ...(template.autoMode || {}), environment: uniq([...tenv, ...menv]) };
  if (!pythonOk) { delete out.hooks; delete out.statusLine; }
  return out;
}

// ---------------------------------------------------------------------------
const python = findPython();
fs.mkdirSync(TARGET, { recursive: true });

// Managed files: everything in the payload except settings.json and the personal templates.
for (const file of walk(PAYLOAD)) {
  const r = rel(file);
  if (r === "settings.json") continue;
  if (r in PERSONAL) continue;                       // rules/secrets-map.md is a template here
  const dest = path.join(TARGET, ...r.split("/"));
  const executable = !IS_WIN && (r.endsWith(".sh") && r !== "hooks/_resolve-python.sh" || r.startsWith("bin/") && !path.extname(r));
  const srcMode = fs.statSync(file).mode & 0o777;
  writeIfChanged(dest, fs.readFileSync(file), executable ? (srcMode | 0o755) : undefined);
}

// Personal files: create once, then never touch.
for (const [r, tmpl] of Object.entries(PERSONAL)) {
  const dest = path.join(TARGET, ...r.split("/"));
  if (fs.existsSync(dest)) continue;
  let body;
  if (tmpl) body = fs.readFileSync(path.join(PAYLOAD, ...tmpl.split("/")));
  else if (r === ".env.local") body = "# Account-level values for every session (KEY=value). Claude files them; see CLAUDE.md Secrets.\n";
  else body = JSON.stringify({ autoMode: { environment: [] }, permissions: { allow: [] } }, null, 2) + "\n";
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, body);
  report.personalCreated.push(r);
}
fs.mkdirSync(path.join(TARGET, "secrets"), { recursive: true });

// settings.json
const settingsPath = path.join(TARGET, "settings.json");
const merged = mergeSettings(readJson(path.join(PAYLOAD, "settings.json"), {}), readJson(settingsPath, {}),
  readJson(path.join(TARGET, "my-settings.json"), {}), Boolean(python));
const settingsChanged = writeIfChanged(settingsPath, Buffer.from(JSON.stringify(merged, null, 2) + "\n"));

// The marker /health reads to know this machine runs the friends' setup.
let version = "unknown";
const g = spawnSync("git", ["-C", HERE, "rev-parse", "--short", "HEAD"], { encoding: "utf8", windowsHide: true });
if (g.status === 0) version = g.stdout.trim();
writeIfChanged(path.join(TARGET, ".friends-setup"),
  Buffer.from(JSON.stringify({ installedFrom: "https://github.com/FabGemYT/FabFriendsClaudeSetup", version }, null, 2) + "\n"));

// Skills that are fetched from their own source rather than copied (licence reasons, CREDITS.md).
const downloads = [];
if (!flag("--no-downloads")) {
  const credits = fs.existsSync(path.join(HERE, "CREDITS.md")) ? fs.readFileSync(path.join(HERE, "CREDITS.md"), "utf8") : "";
  for (const m of credits.matchAll(/The installer runs `([^`]+)`/g)) {
    const name = (m[1].match(/--skill\s+(\S+)/) || [])[1];
    if (name && fs.existsSync(path.join(TARGET, "skills", name, "SKILL.md"))) continue;
    const parts = m[1].split(/\s+/);
    const r = spawnSync(parts[0], parts.slice(1), { encoding: "utf8", shell: IS_WIN, windowsHide: true, timeout: 180000 });
    downloads.push(`${name || m[1]}: ${r.status === 0 ? "installed" : "could not be installed now (run again later)"}`);
  }
}

// A quick proof the guards answer correctly on this machine.
let tests = "skipped";
let testsOk = true;
if (python && !flag("--no-tests")) {
  const home = path.dirname(TARGET);
  const env = { ...process.env, HOME: home, USERPROFILE: home, CLAUDE_HOOK_PYTHON: python.exe };
  const results = [];
  for (const t of ["test-guard-tamper.py", "test-routine-work.py", "test-backup-lock.py"]) {
    const p = path.join(TARGET, "hooks", "tests", t);
    if (!fs.existsSync(p)) continue;
    const r = spawnSync(python.exe, [p], { encoding: "utf8", env, windowsHide: true, timeout: 600000 });
    const summary = ((r.stdout || "").match(/^SUMMARY:.*$/m) || ["no summary"])[0];
    results.push(`${t.replace(/^test-|\.py$/g, "")} ${summary.replace("SUMMARY: ", "")}`);
    if (r.status !== 0) testsOk = false;
  }
  tests = results.join("; ");
}

console.log(`\nINSTALLED into ${TARGET}`);
console.log(`  files: ${report.added} added, ${report.updated} updated, ${report.same} unchanged` +
  (report.backedUp ? `; ${report.backedUp} older version(s) saved in ${BACKUP}` : ""));
if (report.personalCreated.length) console.log(`  created for the owner (never overwritten): ${report.personalCreated.join(", ")}`);
console.log(`  settings.json: ${settingsChanged ? "updated" : "unchanged"}`);
if (downloads.length) console.log(`  downloaded skills: ${downloads.join("; ")}`);
if (!python) {
  console.log("\nPYTHON 3 IS MISSING. The files are installed, but the safety guards are NOT switched on:");
  console.log("without Python they would block every command. Install Python 3, then run this again.");
  process.exit(3);
}
console.log(`  safety guards: ON (Python: ${python.exe})`);
console.log(`  guard check: ${tests}`);
if (!testsOk) { console.log("\nA GUARD CHECK FAILED. Do not use this setup until it is fixed."); process.exit(4); }
console.log("\nRestart Claude Code so the new rules, settings and hooks load.");
