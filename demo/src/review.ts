import { authFetch, mountUserBadge, requireSession, STAFF } from "./auth";
import { $, API, errorText, structName } from "./util";

const session = requireSession(STAFF);
const role = session.user.role;
const canAuthor = role === "CONTENT_EDITOR" || role === "SUPER_ADMIN";
const canDecide = role === "MEDICAL_REVIEWER" || role === "SUPER_ADMIN";

type Task = {
  thread_id: string;
  lesson_id: string;
  structure_id: string;
  status: string;
  draft_text: string;
  created_by: string;
  reviewer: string | null;
  notes: string | null;
  updated_at: string;
};

const STATUS_LABEL: Record<string, string> = {
  MEDICAL_REVIEW: "Awaiting medical review",
  APPROVED: "Approved",
  CONTENT_REVIEW: "Sent back",
  PUBLISHED: "Published",
};

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await authFetch(`${API}${path}`, init);
  if (!res.ok) {
    // FastAPI puts the reason in `detail`
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch { }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// ---- "Draft with AI" box (editors) ----

async function loadStructures(lessonId: string) {
  let rows: { id: string; name_en: string }[] = [];
  try {
    rows = await api(`/api/v1/lessons/${encodeURIComponent(lessonId)}/structures`);
  } catch { }
  $("author-structure").replaceChildren(...rows.map(s => new Option(s.name_en, s.id)));
}

async function generateDraft() {
  const btn = $<HTMLButtonElement>("author-btn");
  const status = $("author-status");
  const lessonId = $<HTMLSelectElement>("author-lesson").value;
  const structureId = $<HTMLSelectElement>("author-structure").value;
  if (!structureId) return;

  btn.disabled = true;
  status.className = "";
  status.textContent = "Drafting… (calls the LLM, may take a few seconds)";
  try {
    const query = new URLSearchParams({ structure_id: structureId });
    const task = await post<Task>(`/api/v1/admin/lessons/${encodeURIComponent(lessonId)}/author?${query}`);
    status.textContent = `Draft for ${structName(task.structure_id)} is waiting for medical review.`;
    status.className = "ok";
    $<HTMLSelectElement>("review-filter").value = "MEDICAL_REVIEW";
    loadQueue();
  } catch (e) {
    status.textContent = `Could not draft (${errorText(e)})`;
    status.className = "warn";
  } finally {
    btn.disabled = false;
  }
}

async function setupAuthoring() {
  if (!canAuthor) return;
  $("author-box").hidden = false;

  const lessonPicker = $<HTMLSelectElement>("author-lesson");
  let lessons: { id: string; title: string }[] = [];
  try {
    lessons = await api("/api/v1/lessons");
  } catch { }
  lessonPicker.replaceChildren(...lessons.map(l => new Option(l.title, l.id)));
  lessonPicker.onchange = () => loadStructures(lessonPicker.value);
  if (lessons.length) await loadStructures(lessonPicker.value);

  $("author-btn").onclick = generateDraft;
}


function reviewCard(task: Task): HTMLElement {
  const card = document.createElement("article");
  card.className = "review-card";
  card.dataset.thread = task.thread_id;
  card.innerHTML = `
    <header><b class="rc-title"></b><span class="pill"></span></header>
    <p class="rc-text"></p>
    <small class="rc-meta"></small>`;

  card.querySelector(".rc-title")!.textContent = `${task.lesson_id} · ${structName(task.structure_id)}`;
  card.querySelector(".rc-text")!.textContent = task.draft_text;

  const pill = card.querySelector(".pill")!;
  pill.textContent = STATUS_LABEL[task.status] ?? task.status;
  pill.classList.add(`s-${task.status.toLowerCase()}`);

  const meta = [`Drafted by ${task.created_by}`];
  if (task.reviewer) meta.push(`reviewed by ${task.reviewer}`);
  if (task.notes) meta.push(`notes: ${task.notes}`);
  card.querySelector(".rc-meta")!.textContent = meta.join(" · ");

  if (task.status === "MEDICAL_REVIEW" && canDecide) {
    card.appendChild(decisionBox(task));
  }
  return card;
}

function decisionBox(task: Task): HTMLElement {
  const box = document.createElement("div");
  box.className = "decide";
  box.innerHTML = `
    <input class="rc-notes" placeholder="Notes for the editor (optional)" aria-label="Review notes">
    <div class="row">
      <button type="button" class="primary approve">Approve</button>
      <button type="button" class="reject">Send back</button>
    </div>
    <p class="rc-status" role="status"></p>`;

  const buttons = box.querySelectorAll("button");
  const notes = box.querySelector<HTMLInputElement>(".rc-notes")!;

  async function decide(decision: "approve" | "reject") {
    buttons.forEach(b => (b.disabled = true));
    try {
      await post(`/api/v1/admin/review/${encodeURIComponent(task.thread_id)}`,
                 { decision, notes: notes.value.trim() });
      loadQueue();
    } catch (e) {
      box.querySelector(".rc-status")!.textContent = `Could not save (${errorText(e)})`;
      buttons.forEach(b => (b.disabled = false));
    }
  }

  box.querySelector<HTMLButtonElement>(".approve")!.onclick = () => decide("approve");
  box.querySelector<HTMLButtonElement>(".reject")!.onclick = () => decide("reject");
  return box;
}

async function loadQueue() {
  const status = $("review-status");
  const list = $("review-list");
  const filter = $<HTMLSelectElement>("review-filter").value;
  status.className = "";
  status.textContent = "Loading…";

  let tasks: Task[];
  try {
    tasks = await api<Task[]>(`/api/v1/admin/reviews?${new URLSearchParams({ status: filter })}`);
  } catch (e) {
    list.replaceChildren();
    status.textContent = `Could not load the queue (${errorText(e)})`;
    status.className = "warn";
    return;
  }

  list.replaceChildren(...tasks.map(reviewCard));
  if (!tasks.length) {
    status.textContent = "Nothing here yet.";
  } else if (!canDecide && filter === "MEDICAL_REVIEW") {
    status.textContent = "Only a medical reviewer can approve drafts.";
  } else {
    status.textContent = "";
  }
}

mountUserBadge(session);
$("review-filter").onchange = loadQueue;
setupAuthoring();
loadQueue();
