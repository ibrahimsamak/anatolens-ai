import { defineConfig, type Plugin } from "vite";
import { createReadStream, existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { parse } from "yaml";

const CONTENT = resolve(__dirname, "../content");
const MIME: Record<string, string> = { glb: "model/gltf-binary", usdz: "model/vnd.usdz+zip", png: "image/png" };

function lessonDirs(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const d of readdirSync(CONTENT)) {
    const f = join(CONTENT, d, "lesson.yaml");
    if (existsSync(f)) out[parse(readFileSync(f, "utf8")).id] = join(CONTENT, d);
  }
  return out;
}

function contentPacks(): Plugin {
  return {
    name: "anatolens-content",
    configureServer(server) {
      server.middlewares.use("/assets", (req, res, next) => {
        const name = decodeURIComponent((req.url ?? "").split("?")[0]).replace(/^\/+/, "");
        if (name.includes("..")) return next();
        const file = Object.values(lessonDirs()).map(d => join(d, "assets", name)).find(existsSync);
        if (!file) return next();
        res.setHeader("Content-Type", MIME[name.split(".").pop() ?? ""] ?? "application/octet-stream");
        res.setHeader("Content-Length", statSync(file).size);
        createReadStream(file).pipe(res);
      });
      server.middlewares.use("/hotspots", (req, res, next) => {
        const id = decodeURIComponent((req.url ?? "").split("?")[0]).replace(/^\/+|\.json$/g, "");
        const dir = lessonDirs()[id];
        if (!dir || !existsSync(join(dir, "hotspots.yaml"))) return next();
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify(parse(readFileSync(join(dir, "hotspots.yaml"), "utf8")) ?? []));
      });
    },
  };
}

export default defineConfig({
  plugins: [contentPacks()],
  server: { port: 5173, host: true },
});
