import "@google/model-viewer";
import { bestARMode, startPseudoAR } from "./ar";

const API: string = import.meta.env.VITE_API ?? "";
const LESSON = new URLSearchParams(location.search).get("lesson") ?? "spine_001";

type Structure = { id: string; mesh_name: string; name_en: string; name_ar: string | null };
type Hotspot = { structure_id: string; position: string; normal: string };
type Done = { done: true; citations: string[]; grounded: boolean };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
type MVMaterial = { name: string; setEmissiveFactor(rgb: [number, number, number]): void };
const mv = $<HTMLElement & {
  src: string; iosSrc: string; canActivateAR?: boolean; activateAR(): void;
  model?: { materials: MVMaterial[] }; materialFromPoint(x: number, y: number): MVMaterial | null;
}>("mv");
const panel = $("panel"), status = $("lesson-status");
const byMaterial = new Map<string, Structure>();
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
    document.title = `${lesson.title} · AnatoLens`;
    mv.src = lesson.model_url;
    if (lesson.ios_model_url) mv.iosSrc = lesson.ios_model_url;

    const [structures, hotspots] = await Promise.all([
      getJSON<Structure[]>(`${API}/api/v1/lessons/${LESSON}/structures`),
      getJSON<Hotspot[]>(`/hotspots/${LESSON}.json`).catch(() => [] as Hotspot[]),
    ]);
    const anchor = new Map(hotspots.map(h => [h.structure_id, h]));
    for (const s of structures) {
      if (s.mesh_name) byMaterial.set(`${s.mesh_name}_mat`, s).set(s.mesh_name, s);
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
  highlight();
  explain(s, "");
}

function highlight() {
  for (const m of mv.model?.materials ?? []) {
    const on = active !== null && byMaterial.get(m.name)?.id === active.id;
    m.setEmissiveFactor(on ? [0.45, 0.16, 0.02] : [0, 0, 0]);
  }
}
mv.addEventListener("load", highlight);

let down: { x: number; y: number } | null = null;
mv.addEventListener("pointerdown", e => { down = { x: e.clientX, y: e.clientY }; });
mv.addEventListener("click", e => {
  const moved = down ? Math.hypot(e.clientX - down.x, e.clientY - down.y) : 0;
  if (moved > 6 || (e.target as HTMLElement).closest(".hotspot")) return;
  const s = byMaterial.get(mv.materialFromPoint(e.clientX, e.clientY)?.name ?? "");
  if (s) select(s);
});

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

type QuizQuestion = { id: string; prompt: string; choices: string[]; difficulty: string; structure_id: string };
type QuizResult = { correct: boolean; mastery: number; reward: number };
type ProgressRow = { structure_id: string; mastery: number; attempts: number };

const USER = new URLSearchParams(location.search).get("user") ?? "demo-user";
$("results-link").setAttribute("href", `/results.html?${new URLSearchParams({ user: USER, lesson: LESSON })}`);

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function quiz() {
  const box = $("quiz"), meta = $("quiz-meta"), prompt = $("quiz-prompt"), choices = $("quiz-choices"),
        feedback = $("quiz-feedback"), next = $<HTMLButtonElement>("quiz-next");
  box.hidden = false;
  next.hidden = true;
  choices.replaceChildren();
  prompt.textContent = "";
  feedback.textContent = "";
  feedback.className = "";
  meta.textContent = "Picking your next question…";
  let q: QuizQuestion;
  try {
    q = await postJSON<QuizQuestion>(`${API}/api/v1/quiz/next`, { user_id: USER, lesson_id: LESSON });
  } catch (e) {
    meta.textContent = `Could not load a question (${(e as Error).message})`;
    next.textContent = "Try again";
    next.hidden = false;
    return;
  }
  meta.textContent = `${q.difficulty} · ${q.structure_id.split(".").pop()!.replace(/_/g, " ")}`;
  prompt.textContent = q.prompt;
  for (const c of q.choices) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = c;
    b.onclick = () => answer(q, c, b);
    choices.appendChild(b);
  }
}

async function answer(q: QuizQuestion, choice: string, picked: HTMLButtonElement) {
  const buttons = [...$("quiz-choices").querySelectorAll("button")];
  buttons.forEach(b => (b.disabled = true));
  const feedback = $("quiz-feedback"), next = $<HTMLButtonElement>("quiz-next");
  try {
    const res = await postJSON<QuizResult>(`${API}/api/v1/quiz/submit`, { user_id: USER, question_id: q.id, answer: choice });
    picked.classList.add(res.correct ? "right" : "wrong");
    feedback.textContent = res.correct ? "Correct!" : "Not quite.";
    feedback.className = res.correct ? "ok" : "warn";
    showProgress();
  } catch (e) {
    feedback.textContent = `Could not submit (${(e as Error).message})`;
    feedback.className = "warn";
    buttons.forEach(b => (b.disabled = false));
    return;
  }
  next.textContent = "Next question";
  next.hidden = false;
}

async function showProgress() {
  const list = $("quiz-progress");
  try {
    const rows = await getJSON<ProgressRow[]>(`${API}/api/v1/progress/${encodeURIComponent(USER)}`);
    list.replaceChildren(...rows.map(p => {
      const li = document.createElement("li");
      li.textContent = `${p.structure_id.split(".").pop()!.replace(/_/g, " ")}: ${Math.round(p.mastery * 100)}% (${p.attempts})`;
      li.style.setProperty("--m", String(p.mastery));
      return li;
    }));
  } catch {  }
}

$("quiz-btn").onclick = quiz;
$("quiz-next").onclick = quiz;

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

type ScanResult = { lesson_id: string | null; confidence: number; decision: "auto" | "confirm" | "rescan" };

let scanStream: MediaStream | null = null;

function setScanStatus(text: string, cls = "") {
  const s = $("scan-status");
  s.textContent = text;
  s.className = cls;
}

async function openScan() {
  $("scan").hidden = false;
  $("scan-open").hidden = true;
  setScanStatus("Point the camera at a lesson page");
  const video = $<HTMLVideoElement>("scan-video"), capture = $<HTMLButtonElement>("scan-capture");
  try {
    scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    video.srcObject = scanStream;
    await video.play();
    capture.hidden = false;
  } catch {
    capture.hidden = true;
    setScanStatus("Camera not available here. Use “Upload photo” instead.", "error");
  }
}

function closeScan() {
  scanStream?.getTracks().forEach(t => t.stop());
  scanStream = null;
  $<HTMLVideoElement>("scan-video").srcObject = null;
  $("scan").hidden = true;
}

function captureFrame(): Promise<Blob> {
  const video = $<HTMLVideoElement>("scan-video");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d")!.drawImage(video, 0, 0);
  return new Promise((ok, fail) => canvas.toBlob(b => (b ? ok(b) : fail(new Error("capture failed"))), "image/jpeg", 0.92));
}

async function recognize(image: Blob) {
  const open = $<HTMLButtonElement>("scan-open");
  open.hidden = true;
  setScanStatus("Recognizing…");
  try {
    const form = new FormData();
    form.append("file", image, "scan.jpg");
    const r = await fetch(`${API}/api/v1/recognition/page`, { method: "POST", body: form });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const res: ScanResult = await r.json();
    const pct = Math.round(res.confidence * 100);
    if (!res.lesson_id || res.decision === "rescan") {
      setScanStatus(`No lesson recognized (${pct}% match). Hold the page straight and fill the frame, then try again.`, "error");
      return;
    }
    const goto = () => { location.search = `?lesson=${encodeURIComponent(res.lesson_id!)}`; };
    if (res.decision === "auto") {
      setScanStatus(`Found ${res.lesson_id} (${pct}% match). Opening…`, "ok");
      closeScan();
      goto();
      return;
    }
    const title = await getJSON<{ title: string }>(`${API}/api/v1/lessons/${res.lesson_id}`)
      .then(l => l.title).catch(() => res.lesson_id!);
    setScanStatus(`Is this “${title}”? (${pct}% match)`);
    open.onclick = () => { closeScan(); goto(); };
    open.hidden = false;
  } catch (e) {
    setScanStatus(`Scan failed (${(e as Error).message})`, "error");
  }
}

async function setupLessonPicker() {
  const select = $<HTMLSelectElement>("lesson-select");
  try {
    const lessons = await getJSON<{ id: string; title: string }[]>(`${API}/api/v1/lessons`);
    select.replaceChildren(...lessons.map(l => new Option(l.title, l.id, false, l.id === LESSON)));
    if (!lessons.some(l => l.id === LESSON)) select.prepend(new Option(LESSON, LESSON, true, true));
  } catch {
    select.replaceChildren(new Option(LESSON, LESSON));
    select.disabled = true;
  }
  select.onchange = () => {
    const qs = new URLSearchParams(location.search);
    qs.set("lesson", select.value);
    location.search = `?${qs}`;
  };
}

$("scan-btn").onclick = openScan;
$("scan-close").onclick = closeScan;
$("scan-capture").onclick = async () => recognize(await captureFrame());
$<HTMLInputElement>("scan-file").onchange = e => {
  const input = e.target as HTMLInputElement, file = input.files?.[0];
  if (file) recognize(file);
  input.value = "";
};

setupLessonPicker();
init();
