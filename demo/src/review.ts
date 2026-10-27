import { authFetch, mountUserBadge, requireSession, STAFF } from "./auth";

const API: string = import.meta.env.VITE_API ?? "";
const session = requireSession(STAFF);
const role = session.user.role;
const canAuthor = role === "CONTENT_EDITOR" || role === "SUPER_ADMIN";
const canDecide = role === "MEDICAL_REVIEWER" || role === "SUPER_ADMIN";
mountUserBadge(session);

type Task = { thread_id: string; lesson_id: string; structure_id: string; status: string; draft_text: string;
              created_by: string; reviewer: string | null; notes: string | null; updated_at: string };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const structName = (id: string) => id.split(".").pop()!.replace(/_/g, " ");
const STATUS_LABEL: Record<string, string> = { MEDICAL_REVIEW: "Awaiting medical review", APPROVED: "Approved",
                                               CONTENT_REVIEW: "Sent back", PUBLISHED: "Published" };

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await authFetch(`${API}${path}`, init);
  if (!r.ok) {
    const detail = await r.json().then(b => b.detail).catch(() => r.statusText);
    throw new Error(`${r.status} ${typeof detail === "string" ? detail : r.statusText}`);
  }
  return r.json();
}
const post = <T>(path: string, body?: unknown) => api<T>(path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });

async function setupAuthoring() {
  if (!canAuthor) return;
  $("author-box").hidden = false;
  const lessonSel = $<HTMLSelectElement>("author-lesson"), structSel = $<HTMLSelectElement>("author-structure");
  const lessons = await api<{ id: string; title: string }[]>("/api/v1/lessons").catch(() => []);
  lessonSel.replaceChildren(...lessons.map(l => new Option(l.title, l.id)));
  const loadStructures = async () => {
    const rows = await api<{ id: string; name_en: string }[]>(`/api/v1/lessons/${encodeURIComponent(lessonSel.value)}/structures`)
      .catch(() => []);
    structSel.replaceChildren(...rows.map(s => new Option(s.name_en, s.id)));
  };
  lessonSel.onchange = loadStructures;
  if (lessons.length) await loadStructures();

  $("author-btn").onclick = async () => {
    const btn = $<HTMLButtonElement>("author-btn"), status = $("author-status");
    if (!structSel.value) return;
    btn.disabled = true;
    status.className = "";
    status.textContent = "Drafting… (calls the LLM, may take a few seconds)";
    try {
      const t = await post<Task>(`/api/v1/admin/lessons/${encodeURIComponent(lessonSel.value)}/author?` +
                                 new URLSearchParams({ structure_id: structSel.value }));
      status.textContent = `Draft for ${structName(t.structure_id)} is waiting for medical review.`;
      status.className = "ok";
      $<HTMLSelectElement>("review-filter").value = "MEDICAL_REVIEW";
      loadQueue();
    } catch (e) {
      status.textContent = `Could not draft (${(e as Error).message})`;
      status.className = "warn";
    } finally {
      btn.disabled = false;
    }
  };
}

function card(t: Task): HTMLElement {
  const el = document.createElement("article");
  el.className = "review-card";
  el.dataset.thread = t.thread_id;
  el.innerHTML = `<header><b class="rc-title"></b><span class="pill"></span></header>
    <p class="rc-text"></p><small class="rc-meta"></small>`;
  el.querySelector(".rc-title")!.textContent = `${t.lesson_id} · ${structName(t.structure_id)}`;
  const pill = el.querySelector(".pill")!;
  pill.textContent = STATUS_LABEL[t.status] ?? t.status;
  pill.classList.add(`s-${t.status.toLowerCase()}`);
  el.querySelector(".rc-text")!.textContent = t.draft_text;
  el.querySelector(".rc-meta")!.textContent = [`Drafted by ${t.created_by}`, t.reviewer && `reviewed by ${t.reviewer}`,
    t.notes && `notes: ${t.notes}`].filter(Boolean).join(" · ");

  if (t.status === "MEDICAL_REVIEW" && canDecide) {
    const box = document.createElement("div");
    box.className = "decide";
    box.innerHTML = `<input class="rc-notes" placeholder="Notes for the editor (optional)" aria-label="Review notes">
      <div class="row"><button type="button" class="primary approve">Approve</button>
      <button type="button" class="reject">Send back</button></div><p class="rc-status" role="status"></p>`;
    const decide = async (decision: "approve" | "reject") => {
      box.querySelectorAll("button").forEach(b => (b.disabled = true));
      try {
        await post(`/api/v1/admin/review/${encodeURIComponent(t.thread_id)}`,
                   { decision, notes: box.querySelector<HTMLInputElement>(".rc-notes")!.value.trim() });
        loadQueue();
      } catch (e) {
        box.querySelector(".rc-status")!.textContent = `Could not save (${(e as Error).message})`;
        box.querySelectorAll("button").forEach(b => (b.disabled = false));
      }
    };
    box.querySelector<HTMLButtonElement>(".approve")!.onclick = () => decide("approve");
    box.querySelector<HTMLButtonElement>(".reject")!.onclick = () => decide("reject");
    el.appendChild(box);
  }
  return el;
}

async function loadQueue() {
  const status = $("review-status"), list = $("review-list"), filter = $<HTMLSelectElement>("review-filter").value;
  status.className = "";
  status.textContent = "Loading…";
  try {
    const tasks = await api<Task[]>(`/api/v1/admin/reviews?${new URLSearchParams({ status: filter })}`);
    list.replaceChildren(...tasks.map(card));
    status.textContent = tasks.length ? (canDecide || filter !== "MEDICAL_REVIEW" ? "" : "Only a medical reviewer can approve drafts.")
                                      : "Nothing here yet.";
  } catch (e) {
    list.replaceChildren();
    status.textContent = `Could not load the queue (${(e as Error).message})`;
    status.className = "warn";
  }
}

$("review-filter").onchange = loadQueue;
setupAuthoring();
loadQueue();
