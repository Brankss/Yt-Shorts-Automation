#!/usr/bin/env node
/**
 * Export the artwork the dilemma bank references into the video project.
 *
 * The session's egress policy blocks every image CDN, so artwork comes from an
 * npm package instead — the npm registry is reachable directly. This reads the
 * `noto:<name>` references in content/dilemmas.json and writes one standalone
 * SVG per icon into the composition's assets directory, so the render has real
 * files on disk and never fetches anything.
 *
 * Set `--set` to point at a different Iconify package if the artwork changes.
 *
 * Usage:
 *   node scripts/export_icons.mjs
 *   node scripts/export_icons.mjs --out videos/wyr-template/assets
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function arg(name, fallback) {
  const i = process.argv.indexOf("--" + name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const OUT = path.resolve(ROOT, arg("out", "videos/wyr-template/assets"));
const PKG = arg("set", "@iconify-json/noto");
const PREFIX = PKG.split("/").pop().replace(/^noto$/, "noto");

const iconsPath = path.join(ROOT, "videos/wyr-template/node_modules", PKG, "icons.json");
if (!fs.existsSync(iconsPath)) {
  console.error(
    "ERROR: " + PKG + " is not installed.\n" +
    "  cd videos/wyr-template && npm install " + PKG
  );
  process.exit(1);
}

const set = JSON.parse(fs.readFileSync(iconsPath, "utf8"));
const bank = JSON.parse(fs.readFileSync(path.join(ROOT, "content/dilemmas.json"), "utf8"));

// Collect every icon the bank asks for, once.
const wanted = new Set();
for (const d of bank.dilemmas) {
  for (const key of ["image_a", "image_b"]) {
    const ref = d[key];
    if (!ref) continue;
    const [prefix, name] = ref.split(":");
    if (prefix !== PREFIX) {
      console.error(`  skip ${d.id}.${key}: ${ref} is not from ${PREFIX}`);
      continue;
    }
    wanted.add(name);
  }
}

fs.mkdirSync(OUT, { recursive: true });

let written = 0;
const missing = [];
for (const name of [...wanted].sort()) {
  const icon = set.icons[name];
  if (!icon) {
    missing.push(name);
    continue;
  }
  // Iconify stores the inner markup plus per-icon or per-set dimensions.
  const w = icon.width ?? set.width ?? 24;
  const h = icon.height ?? set.height ?? 24;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" ` +
    `width="${w}" height="${h}">${icon.body}</svg>\n`;
  fs.writeFileSync(path.join(OUT, `${PREFIX}-${name}.svg`), svg);
  written++;
}

console.log(`${written} icon(s) written to ${path.relative(ROOT, OUT)}`);
if (missing.length) {
  console.error(`MISSING from ${PKG}: ${missing.join(", ")}`);
  process.exit(1);
}
