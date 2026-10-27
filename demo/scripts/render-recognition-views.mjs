// Renders reference views of each lesson model into content/<pack>/assets/recognition/, which ingest
// embeds for page recognition. Needs the backend and `npm run dev` running; then re-run ingestion.
//   node scripts/render-recognition-views.mjs [http://localhost:5173]
import { chromium } from "playwright";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { parse } from "yaml";

const BASE = process.argv[2] ?? "http://localhost:5173";
const CONTENT = resolve(import.meta.dirname, "../../content");
const ANGLES = ["0deg", "90deg", "180deg", "270deg"];

const packs = readdirSync(CONTENT)
  .filter(d => existsSync(join(CONTENT, d, "lesson.yaml")))
  .map(d => ({ dir: join(CONTENT, d), id: parse(readFileSync(join(CONTENT, d, "lesson.yaml"), "utf8")).id }));

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 640, height: 640 } });

// the lesson page asks for a sign-in first. The lesson endpoints themselves are public, so a local
// session with an unexpired token-shaped value is enough to get past the redirect.
const b64 = obj => Buffer.from(JSON.stringify(obj)).toString("base64url");
const token = `${b64({ alg: "none" })}.${b64({ exp: Math.floor(Date.now() / 1000) + 3600 })}.x`;
const session = { access_token: token, refresh_token: token,
                  user: { id: "render-script", email: "", role: "STUDENT", display_name: "render script" } };
await page.addInitScript(s => localStorage.setItem("anatolens.session", s), JSON.stringify(session));

for (const { dir, id } of packs) {
  await page.goto(`${BASE}/?lesson=${id}`);
  await page.waitForFunction(() => document.querySelector("#mv")?.loaded, null, { timeout: 60000 });
  // labels are text the photo may not have; keep the references to the model itself
  await page.addStyleTag({ content: ".hotspot, #lesson-status { display: none !important; }" });
  const out = join(dir, "assets", "recognition");
  mkdirSync(out, { recursive: true });
  for (const angle of ANGLES) {
    await page.$eval("#mv", (mv, a) => { mv.cameraOrbit = `${a} 75deg auto`; mv.jumpCameraToGoal(); }, angle);
    await page.waitForTimeout(800);
    await (await page.$("#mv")).screenshot({ path: join(out, `view_${angle}.jpg`), type: "jpeg", quality: 85 });
  }
  console.log(`${id}: ${ANGLES.length} views -> ${out}`);
}
await browser.close();
