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
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail?.missing) detail = `${body.detail.detail}: ${body.detail.missing.map(structName).join(", ")}`;
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

type Proposal = {
  id: string;
  lesson_id: string;
  subject_id: string;
  predicate: string;
  object_id: string;
  confidence: number;
  status: string;
  conflict: boolean;
};

type Mesh = { id: string; lesson_id: string; url: string; status: string; reason: string };

type Analysis = {
  regions: { label: string | null; structure_id: string | null }[];
  proposals: Proposal[];
  known: { subject_id: string; predicate: string; object_id: string }[];
  mesh: Mesh | null;
  notes: string[];
};

const SUGGEST_LABEL: Record<string, string> = {
  AI_GENERATED: "Awaiting review",
  APPROVED: "Approved",
  DRAFT: "Rejected",
};

function el(tag: string, className: string, text = ""): HTMLElement {
  const e = document.createElement(tag);
  e.className = className;
  e.textContent = text;
  return e;
}

async function analyze() {
  const btn = $<HTMLButtonElement>("analyze-btn");
  const status = $("analyze-status");
  const file = $<HTMLInputElement>("analyze-file").files?.[0];
  if (!file) return;

  const lessonId = encodeURIComponent($<HTMLSelectElement>("analyze-lesson").value);
  const make3d = $<HTMLInputElement>("analyze-3d").checked;
  const form = new FormData();
  form.append("file", file);

  btn.disabled = true;
  status.className = "";
  status.textContent = "Analyzing… (vision model, may take a while)";
  try {
    const r = await api<Analysis>(`/api/v1/admin/lessons/${lessonId}/analyze?make_3d=${make3d}`,
                                  { method: "POST", body: form });
    const links = [...r.proposals, ...r.known];
    const ids = [...r.regions.map(x => x.structure_id), ...links.flatMap(l => [l.subject_id, l.object_id])];
    const found = [...new Set(ids.filter(Boolean) as string[])].map(structName);
    const lines = [`Found parts: ${found.join(", ") || "none"}`,
                   `Found ${links.length} link(s): ${r.proposals.length} new sent for review, ${r.known.length} already known`];
    if (r.mesh) lines.push(r.mesh.status === "DRAFT" ? `3D model rejected: ${r.mesh.reason}` : "3D model sent for review");
    status.textContent = [...lines, ...r.notes].join("\n");
    status.className = r.proposals.length || r.mesh ? "ok" : "warn";
    $<HTMLSelectElement>("suggest-filter").value = "AI_GENERATED";
    loadSuggestions();
  } catch (e) {
    status.textContent = `Could not analyze (${errorText(e)})`;
    status.className = "warn";
  } finally {
    btn.disabled = false;
  }
}

async function setupAnalyze() {
  if (!canAuthor) return;
  $("analyze-box").hidden = false;

  let lessons: { id: string; title: string }[] = [];
  try {
    lessons = await api("/api/v1/lessons");
  } catch { }
  $("analyze-lesson").replaceChildren(...lessons.map(l => new Option(l.title, l.id)));

  const fileInput = $<HTMLInputElement>("analyze-file");
  fileInput.onchange = () => {
    const file = fileInput.files?.[0];
    $<HTMLButtonElement>("analyze-btn").disabled = !file;
    $("analyze-status").textContent = file?.name ?? "";
  };
  $("analyze-btn").onclick = analyze;
}

function suggestionCard(title: string, status: string, path: string, ...content: HTMLElement[]): HTMLElement {
  const card = el("article", "review-card");
  const header = document.createElement("header");
  header.append(el("b", "rc-title", title), el("span", `pill s-${status.toLowerCase()}`, SUGGEST_LABEL[status] ?? status));
  card.append(header, ...content);

  if (status !== "AI_GENERATED" || !canDecide) return card;

  const approve = el("button", "primary", "Approve") as HTMLButtonElement;
  const reject = el("button", "", "Reject") as HTMLButtonElement;
  const error = el("p", "rc-status");
  const row = el("div", "row");
  row.append(approve, reject);
  const box = el("div", "decide");
  box.append(row, error);
  card.append(box);

  const decide = async (decision: string) => {
    approve.disabled = reject.disabled = true;
    try {
      await post(`${path}/${decision}`);
      loadSuggestions();
    } catch (e) {
      error.textContent = `Could not save (${errorText(e)})`;
      approve.disabled = reject.disabled = false;
    }
  };
  approve.onclick = () => decide("approve");
  reject.onclick = () => decide("reject");
  return card;
}

function proposalCard(p: Proposal): HTMLElement {
  const edge = el("p", "rc-edge",
    `${structName(p.subject_id)} → ${p.predicate.replace("_", " ")} → ${structName(p.object_id)}`);
  const meta = el("small", "rc-meta", `confidence ${Math.round(p.confidence * 100)}%`);
  const card = suggestionCard(`${p.lesson_id} · link`, p.status, `/api/v1/admin/proposals/${encodeURIComponent(p.id)}`, edge, meta);
  if (p.conflict) {
    card.classList.add("conflict");
    card.querySelector("header")!.append(el("span", "pill conflict", "Contradicts approved anatomy"));
  }
  return card;
}

function meshCard(m: Mesh): HTMLElement {
  const link = el("a", "", "Download model") as HTMLAnchorElement;
  link.href = m.url;
  link.target = "_blank";
  const reason = el("small", "rc-meta", m.reason === "ok" ? "" : m.reason);
  return suggestionCard(`${m.lesson_id} · 3D model`, m.status, `/api/v1/admin/meshes/${encodeURIComponent(m.id)}`,
                        link, document.createElement("br"), reason);
}

async function loadSuggestions() {
  const status = $("suggest-status");
  const list = $("suggest-list");
  const query = `status=${$<HTMLSelectElement>("suggest-filter").value}`;
  status.className = "";
  status.textContent = "Loading…";

  try {
    const [proposals, meshes] = await Promise.all([
      api<Proposal[]>(`/api/v1/admin/proposals?${query}`),
      api<Mesh[]>(`/api/v1/admin/meshes?${query}`),
    ]);
    list.replaceChildren(...proposals.map(proposalCard), ...meshes.map(meshCard));
    status.textContent = proposals.length || meshes.length ? "" : "Nothing here yet.";
  } catch (e) {
    list.replaceChildren();
    status.textContent = `Could not load suggestions (${errorText(e)})`;
    status.className = "warn";
  }
}

mountUserBadge(session);
$("review-filter").onchange = loadQueue;
$("suggest-filter").onchange = loadSuggestions;
setupAuthoring();
setupAnalyze();
loadQueue();
loadSuggestions();
