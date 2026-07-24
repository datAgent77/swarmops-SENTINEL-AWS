#!/usr/bin/env bash
# Record the hero GIF (docs/img/demo.gif) from a LIVE local run, so the ENV chip
# shows your real provider (openai / gemini / …) instead of mock.
#
# Prereqs:
#   - The app running locally: in one terminal `make demo` (or make api + make web),
#     with your provider key set in apps/api/.env (e.g. OPENAI_API_KEY or GEMINI_API_KEY
#     + LLM_PROVIDER). Optionally BAND_API_KEY/SENSO_API_KEY/PIONEER_KEY to show the TOOLS chip.
#   - ffmpeg installed:  brew install ffmpeg
#   - node + npm (you already have these).
#
# Usage:  bash scripts/record-demo-gif.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/docs/img/demo.gif"
URL="${URL:-http://localhost:3000}"

command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg not found — run: brew install ffmpeg"; exit 1; }
curl -sf "$URL" >/dev/null 2>&1 || { echo "App not reachable at $URL — start it with 'make demo' first."; exit 1; }

WORK="$(mktemp -d)"; FRAMES="$WORK/frames"; mkdir -p "$FRAMES"
trap 'rm -rf "$WORK"' EXIT
echo "Installing a headless browser (one-time, into a temp dir)…"
( cd "$WORK" && npm init -y >/dev/null 2>&1 && npm i playwright >/dev/null 2>&1 && npx playwright install chromium >/dev/null 2>&1 )

cat > "$WORK/cap.mjs" <<'JS'
import { chromium } from "playwright";
const URL = process.env.URL || "http://localhost:3000";
const FRAMES = process.env.FRAMES;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 820 }, deviceScaleFactor: 1 });
await p.goto(URL, { waitUntil: "networkidle" });
await p.waitForTimeout(1200);
let i = 0;
const shot = async () => { await p.screenshot({ path: `${FRAMES}/f${String(i).padStart(3,"0")}.png` }); i++; };
await shot(); await shot();
await p.getByText("Run demo mission").click();
let approved = false, done = 0, gate = 0;
for (let t = 0; t < 160; t++) {
  await shot();
  if (!approved) {
    const ap = await p.locator(".approval-panel .solid-ok").count();
    if (ap) { gate++; if (gate >= 4) { try { await p.locator(".approval-panel .solid-ok").click(); approved = true; } catch {} } }
  }
  if (await p.locator(".overlay-card").count()) { done++; if (done > 9) break; }
  await p.waitForTimeout(350);
}
console.log("frames:", i, "approved:", approved);
await b.close();
JS

echo "Recording a demo mission… (make sure the app is idle/ready)"
URL="$URL" FRAMES="$FRAMES" node "$WORK/cap.mjs"

echo "Building GIF → $OUT"
ffmpeg -y -framerate 8 -i "$FRAMES/f%03d.png" \
  -vf "scale=920:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=160[p];[s1][p]paletteuse=dither=bayer" \
  -loop 0 "$OUT"
echo "Done. Wrote $OUT ($(du -h "$OUT" | cut -f1)). Commit it: git add docs/img/demo.gif"
