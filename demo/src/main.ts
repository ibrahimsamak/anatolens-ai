import "@google/model-viewer";
import { bestARMode, startPseudoAR } from "./ar";
import { mountUserBadge, requireSession, STAFF } from "./auth";
import { setupScan } from "./scan";
import { $, API, errorText, getJSON, postJSON, structName } from "./util";

const session = requireSession();
const USER = session.user.id;
const LESSON = new URLSearchParams(location.search).get("lesson") ?? "spine_001";

type Lesson = { title: string; model_url: string; ios_model_url: string | null };
type Structure = { id: string; mesh_name: string; name_en: string; name_ar: string | null };
type Hotspot = { structure_id: string; position: string; normal: string };
type TutorEvent = { token: string } | { done: true; citations: string[]; grounded: boolean };

type Material = { name: string; setEmissiveFactor(rgb: [number, number, number]): void };
type ModelViewer = HTMLElement & {
  src: string;
  iosSrc: string;
  canActivateAR?: boolean;
  activateAR(): void;
  model?: { materials: Material[] };
  materialFromPoint(x: number, y: number): Material | null;
};

const mv = $<ModelViewer>("mv");
const byMaterial = new Map<string, Structure>();   // GLB material name -> structure
let active: Structure | null = null;
let tutorRequest: AbortController | null = null;

function setStatus(text: string, error = false) {
  const el = $("lesson-status");
  el.textContent = text;
  el.classList.toggle("error", error);
}


async function loadLesson() {
  try {
    const lesson = await getJSON<Lesson>(`${API}/api/v1/lessons/${LESSON}`);
    document.title = `${lesson.title} · AnatoLens`;
    mv.src = lesson.model_url;
    if (lesson.ios_model_url) mv.iosSrc = lesson.ios_model_url;

    const structures = await getJSON<Structure[]>(`${API}/api/v1/lessons/${LESSON}/structures`);
    const hotspots = await getJSON<Hotspot[]>(`/hotspots/${LESSON}.json`).catch(() => []);
    const hotspotFor = new Map(hotspots.map(h => [h.structure_id, h]));

    for (const s of structures) {
      if (s.mesh_name) {
        byMaterial.set(`${s.mesh_name}_mat`, s);
        byMaterial.set(s.mesh_name, s);
      }
      addChip(s);
      const h = hotspotFor.get(s.id);
      if (h) addHotspot(s, h);
    }

    if (structures.length) setStatus("Tap a structure to learn about it");
    else setStatus("No structures for this lesson — run ingestion", true);
  } catch (e) {
    setStatus(`Backend unavailable: ${errorText(e)}`, true);
  }
  setupAR();
}

function addChip(s: Structure) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.textContent = s.name_en;
  chip.dataset.sid = s.id;
  chip.onclick = () => select(s);
  $("panel").appendChild(chip);
}

function addHotspot(s: Structure, h: Hotspot) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "hotspot";
  btn.slot = `hotspot-${s.id}`;
  btn.dataset.sid = s.id;
  btn.dataset.position = h.position;
  btn.dataset.normal = h.normal;
  btn.dataset.visibilityAttribute = "visible";
  btn.textContent = s.name_en;
  btn.onclick = () => select(s);
  mv.appendChild(btn);
}

function select(s: Structure) {
  active = s;
  for (const el of document.querySelectorAll<HTMLElement>("[data-sid]")) {
    el.setAttribute("aria-pressed", String(el.dataset.sid === s.id));
  }
  $("ask").hidden = false;
  $("ask-target").textContent = s.name_en;
  highlight();
  explain(s, "");
}

function highlight() {
  for (const m of mv.model?.materials ?? []) {
    const isActive = active !== null && byMaterial.get(m.name)?.id === active.id;
    m.setEmissiveFactor(isActive ? [0.45, 0.16, 0.02] : [0, 0, 0]);
  }
}

mv.addEventListener("load", highlight);

let pointerDown = { x: 0, y: 0 };
mv.addEventListener("pointerdown", e => {
  pointerDown = { x: e.clientX, y: e.clientY };
});
mv.addEventListener("click", e => {
  const moved = Math.hypot(e.clientX - pointerDown.x, e.clientY - pointerDown.y);
  if (moved > 6) return;
  if ((e.target as HTMLElement).closest(".hotspot")) return;

  const material = mv.materialFromPoint(e.clientX, e.clientY);
  const s = material ? byMaterial.get(material.name) : undefined;
  if (s) select(s);
});


async function explain(s: Structure, question: string) {
  tutorRequest?.abort();   // only the latest question matters
  const request = new AbortController();
  tutorRequest = request;

  const text = $("card-text");
  const meta = $("card-meta");
  $("card").hidden = false;
  $("card-title").textContent = s.name_en;
  text.textContent = "";
  meta.textContent = "Thinking…";
  meta.className = "";

  try {
    const res = await fetch(`${API}/api/v1/tutor/ask?structure_id=${encodeURIComponent(s.id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, locale: "en" }),
      signal: request.signal,
    });
    if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);

    for await (const ev of readEvents(res.body)) {
      if ("token" in ev) {
        text.textContent += ev.token;
      } else if (ev.grounded) {
        const sources = [...new Set(ev.citations)].join("; ");
        meta.textContent = `Sources: ${sources}`;
        meta.className = "ok";
      } else {
        meta.textContent = "⚠ Not verified";
        meta.className = "warn";
      }
    }
  } catch (e) {
    if (request.signal.aborted) return;
    meta.textContent = `Could not get an explanation (${errorText(e)})`;
    meta.className = "warn";
  }
}

async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<TutorEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() ?? "";   // the last piece may be incomplete
    for (const event of events) {
      const data = event.split(/\r?\n/)
        .filter(line => line.startsWith("data:"))
        .map(line => line.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data);
    }
  }
}

$<HTMLFormElement>("ask").onsubmit = e => {
  e.preventDefault();
  const question = $<HTMLInputElement>("question").value.trim();
  if (active && question) explain(active, question);
};


type QuizQuestion = { id: string; prompt: string; choices: string[]; difficulty: string; structure_id: string };
type QuizResult = { correct: boolean; mastery: number; reward: number };
type ProgressRow = { structure_id: string; mastery: number; attempts: number };

async function nextQuestion() {
  const meta = $("quiz-meta");
  const nextBtn = $<HTMLButtonElement>("quiz-next");
  const feedback = $("quiz-feedback");

  $("quiz").hidden = false;
  nextBtn.hidden = true;
  $("quiz-choices").replaceChildren();
  $("quiz-prompt").textContent = "";
  feedback.textContent = "";
  feedback.className = "";
  meta.textContent = "Picking your next question…";

  let q: QuizQuestion;
  try {
    q = await postJSON<QuizQuestion>(`${API}/api/v1/quiz/next`, { user_id: USER, lesson_id: LESSON });
  } catch (e) {
    meta.textContent = `Could not load a question (${errorText(e)})`;
    nextBtn.textContent = "Try again";
    nextBtn.hidden = false;
    return;
  }

  meta.textContent = `${q.difficulty} · ${structName(q.structure_id)}`;
  $("quiz-prompt").textContent = q.prompt;
  for (const choice of q.choices) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = choice;
    btn.onclick = () => answer(q, choice, btn);
    $("quiz-choices").appendChild(btn);
  }
}

async function answer(q: QuizQuestion, choice: string, picked: HTMLButtonElement) {
  const buttons = [...$("quiz-choices").querySelectorAll("button")];
  const feedback = $("quiz-feedback");
  const nextBtn = $<HTMLButtonElement>("quiz-next");
  buttons.forEach(b => (b.disabled = true));

  try {
    const res = await postJSON<QuizResult>(`${API}/api/v1/quiz/submit`,
                                           { user_id: USER, question_id: q.id, answer: choice });
    if (res.correct) {
      picked.classList.add("right");
      feedback.textContent = "Correct!";
      feedback.className = "ok";
    } else {
      picked.classList.add("wrong");
      feedback.textContent = "Not quite.";
      feedback.className = "warn";
    }
    showProgress();
  } catch (e) {
    feedback.textContent = `Could not submit (${errorText(e)})`;
    feedback.className = "warn";
    buttons.forEach(b => (b.disabled = false));
    return;
  }

  nextBtn.textContent = "Next question";
  nextBtn.hidden = false;
}

async function showProgress() {
  let rows: ProgressRow[];
  try {
    rows = await getJSON<ProgressRow[]>(`${API}/api/v1/progress/${encodeURIComponent(USER)}`);
  } catch {
    return;   
  }
  const items = rows.map(p => {
    const li = document.createElement("li");
    li.textContent = `${structName(p.structure_id)}: ${Math.round(p.mastery * 100)}% (${p.attempts})`;
    li.style.setProperty("--m", String(p.mastery));
    return li;
  });
  $("quiz-progress").replaceChildren(...items);
}

$("quiz-btn").onclick = nextQuestion;
$("quiz-next").onclick = nextQuestion;


async function setupAR() {
  await customElements.whenDefined("model-viewer");
  const mode = await bestARMode(mv);

  if (mode === "webxr" || mode === "native") {
    const arBtn = $<HTMLButtonElement>("ar-btn");
    arBtn.textContent = "View in AR";
    arBtn.onclick = () => mv.activateAR();
    arBtn.hidden = false;
  }

  // Quick Look / Scene Viewer can't show the HTML hotspots, so also offer the camera view, which keeps them
  const hasCamera = typeof navigator.mediaDevices?.getUserMedia === "function";
  if (mode === "pseudo" || (mode === "native" && hasCamera)) {
    const camBtn = $<HTMLButtonElement>("camera-btn");
    let stopCamera: (() => void) | null = null;

    camBtn.onclick = async () => {
      if (stopCamera) {
        stopCamera();
        stopCamera = null;
        camBtn.textContent = "Camera view";
        return;
      }
      try {
        stopCamera = await startPseudoAR($("camera"));
        camBtn.textContent = "Stop camera";
      } catch {
        setStatus("Camera permission denied", true);
      }
    };
    camBtn.hidden = false;
  }
}


async function setupLessonPicker() {
  const picker = $<HTMLSelectElement>("lesson-select");
  try {
    const lessons = await getJSON<{ id: string; title: string }[]>(`${API}/api/v1/lessons`);
    picker.replaceChildren(...lessons.map(l => new Option(l.title, l.id, false, l.id === LESSON)));
    if (!lessons.some(l => l.id === LESSON)) picker.prepend(new Option(LESSON, LESSON, true, true));
  } catch {
    picker.replaceChildren(new Option(LESSON, LESSON));
    picker.disabled = true;
  }

  picker.onchange = () => {
    const params = new URLSearchParams(location.search);
    params.set("lesson", picker.value);
    location.search = `?${params}`;
  };
}

$("results-link").setAttribute("href", `/results.html?${new URLSearchParams({ lesson: LESSON })}`);
$("review-link").hidden = !STAFF.includes(session.user.role);
mountUserBadge(session);

setupScan();
setupLessonPicker();
loadLesson();
