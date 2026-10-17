import "@google/model-viewer";
import { bestARMode, startPseudoAR } from "./ar";

const API: string = import.meta.env.VITE_API ?? "http://localhost:8000";
const LESSON = new URLSearchParams(location.search).get("lesson") ?? "spine_001";

type Structure = { id: string; mesh_name: string; name_en: string; name_ar: string | null };
type Hotspot = { structure_id: string; position: string; normal: string };
type Done = { done: true; citations: string[]; grounded: boolean };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const mv = $<HTMLElement & { src: string; iosSrc: string; canActivateAR?: boolean; activateAR(): void }>("mv");
const panel = $("panel"), status = $("lesson-status");
let active: Structure | null = null;
let inflight: AbortController | null = null;

function setStatus(text: string, error = false) {
  status.textContent = text;
  status.classList.toggle("error", error);
}

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${url}`);
  return r.json();
}

async function init() {
  try {
    const lesson = await getJSON<{ title: string; model_url: string; ios_model_url: string | null }>(
      `${API}/api/v1/lessons/${LESSON}`);
    $("lesson-title").textContent = `· ${lesson.title}`;
    mv.src = lesson.model_url;
    if (lesson.ios_model_url) mv.iosSrc = lesson.ios_model_url;

    const [structures, hotspots] = await Promise.all([
      getJSON<Structure[]>(`${API}/api/v1/lessons/${LESSON}/structures`),
      getJSON<Hotspot[]>(`/hotspots/${LESSON}.json`).catch(() => [] as Hotspot[]),
    ]);
    const anchor = new Map(hotspots.map(h => [h.structure_id, h]));
    for (const s of structures) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.textContent = s.name_en;
      chip.dataset.sid = s.id;
      chip.onclick = () => select(s);
      panel.appendChild(chip);

      const h = anchor.get(s.id);
      if (!h) continue;
      const hs = document.createElement("button");
      hs.type = "button";
      hs.className = "hotspot";
      hs.slot = `hotspot-${s.id}`;
      hs.dataset.sid = s.id;
      hs.dataset.position = h.position;
      hs.dataset.normal = h.normal;
      hs.dataset.visibilityAttribute = "visible";
      hs.textContent = s.name_en;
      hs.onclick = () => select(s);
      mv.appendChild(hs);
    }
    setStatus(structures.length ? "Tap a structure to learn about it" : "No structures for this lesson — run ingestion", !structures.length);
  } catch (e) {
    setStatus(`Backend unavailable: ${(e as Error).message}`, true);
  }
  setupAR();
}

function select(s: Structure) {
  active = s;
  document.querySelectorAll<HTMLElement>("[data-sid]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.sid === s.id)));
  $("ask").hidden = false;
  $("ask-target").textContent = s.name_en;
  explain(s, "");
}

async function explain(s: Structure, question: string) {
  inflight?.abort();
  const ctrl = inflight = new AbortController();
  const card = $("card"), text = $("card-text"), meta = $("card-meta");
  card.hidden = false;
  $("card-title").textContent = s.name_en;
  text.textContent = "";
  meta.textContent = "Thinking…";
  meta.className = "";
  try {
    const r = await fetch(`${API}/api/v1/tutor/ask?structure_id=${encodeURIComponent(s.id)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, locale: "en" }), signal: ctrl.signal,
    });
    if (!r.ok || !r.body) throw new Error(`${r.status} ${r.statusText}`);
    for await (const ev of sse(r.body)) {
      if ("token" in ev) text.textContent += ev.token;
      if ("done" in ev) {
        meta.textContent = ev.grounded ? `Sources: ${[...new Set(ev.citations)].join("; ")}` : "⚠ Not verified";
        meta.className = ev.grounded ? "ok" : "warn";
      }
    }
  } catch (e) {
    if (ctrl.signal.aborted) return;
    meta.textContent = `Could not get an explanation (${(e as Error).message})`;
    meta.className = "warn";
  }
}

async function* sse(body: ReadableStream<Uint8Array>): AsyncGenerator<{ token: string } | Done> {
  const reader = body.getReader(), decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const events = buf.split(/\r?\n\r?\n/);
    buf = events.pop() ?? "";
    for (const ev of events) {
      const data = ev.split(/\r?\n/).filter(l => l.startsWith("data:")).map(l => l.slice(5).trimStart()).join("\n");
      if (data) yield JSON.parse(data);
    }
  }
}

$<HTMLFormElement>("ask").onsubmit = e => {
  e.preventDefault();
  const q = $<HTMLInputElement>("question");
  if (active && q.value.trim()) explain(active, q.value.trim());
};

async function setupAR() {
  await customElements.whenDefined("model-viewer");
  const mode = await bestARMode(mv);
  const btn = $<HTMLButtonElement>("ar-btn");
  if (mode === "webxr" || mode === "native") {
    btn.textContent = "View in AR";
    btn.onclick = () => mv.activateAR();
  } else if (mode === "pseudo") {
    let stop: (() => void) | null = null;
    btn.textContent = "Camera view";
    btn.onclick = async () => {
      if (stop) { stop(); stop = null; btn.textContent = "Camera view"; return; }
      try { stop = await startPseudoAR($("camera")); btn.textContent = "Stop camera"; }
      catch { setStatus("Camera permission denied", true); }
    };
  } else return;
  btn.hidden = false;
}

init();
