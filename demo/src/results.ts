import { mountUserBadge, requireSession } from "./auth";
import { $, API, errorText, getJSON, structName } from "./util";

type HistoryRow = {
  at: string;
  lesson_id: string;
  lesson_title: string;
  structure_id: string;
  difficulty: string;
  prompt: string;
  answer: string;
  correct: boolean;
};
type ProgressRow = { structure_id: string; mastery: number; attempts: number };

const params = new URLSearchParams(location.search);
const LESSON = params.get("lesson");
const session = requireSession();

// students see their own results; teachers and admins can open a student's with ?user=<id>
const canViewOthers = session.user.role === "TEACHER" || session.user.role === "SUPER_ADMIN";
let USER = session.user.id;
let WHO = session.user.display_name;
if (canViewOthers && params.get("user")) {
  USER = params.get("user")!;
  WHO = USER;
}

function grade(pct: number): string {
  if (pct >= 90) return "A";
  if (pct >= 80) return "B";
  if (pct >= 70) return "C";
  if (pct >= 60) return "D";
  return "F";
}

function percent(part: number, total: number): number {
  return Math.round((part / total) * 100);
}

function cell(text: string, cls = ""): HTMLTableCellElement {
  const td = document.createElement("td");
  td.textContent = text;
  if (cls) td.className = cls;
  return td;
}

function row(...cells: HTMLTableCellElement[]): HTMLTableRowElement {
  const tr = document.createElement("tr");
  tr.append(...cells);
  return tr;
}

function showEmpty(body: HTMLElement, columns: number, text: string) {
  const td = cell(text, "empty");
  td.colSpan = columns;
  body.replaceChildren(row(td));
}

function renderTotals(history: HistoryRow[]) {
  const correct = history.filter(h => h.correct).length;
  const status = $("results-status");

  if (!history.length) {
    status.textContent = `No quiz answers yet for ${WHO}. Open a lesson and press “Quiz me”.`;
    $("t-grade").textContent = "–";
    $("t-score").textContent = "–";
  } else {
    const pct = percent(correct, history.length);
    status.textContent = `Results for ${WHO}`;
    $("t-grade").textContent = grade(pct);
    $("t-score").textContent = `${pct}%`;
  }
  $("t-correct").textContent = String(correct);
  $("t-total").textContent = String(history.length);
}

function renderLessons(history: HistoryRow[]) {
  const body = $("lessons-body");
  const byLesson = new Map<string, { title: string; total: number; correct: number }>();
  for (const h of history) {
    if (!byLesson.has(h.lesson_id)) byLesson.set(h.lesson_id, { title: h.lesson_title, total: 0, correct: 0 });
    const lesson = byLesson.get(h.lesson_id)!;
    lesson.total++;
    if (h.correct) lesson.correct++;
  }

  if (!byLesson.size) {
    showEmpty(body, 5, "No lessons quizzed yet");
    return;
  }
  const rows = [...byLesson.values()].map(l => {
    const pct = percent(l.correct, l.total);
    const g = grade(pct);
    return row(cell(l.title), cell(String(l.total), "num"), cell(String(l.correct), "num"),
               cell(`${pct}%`, "num"), cell(g, `grade grade-${g}`));
  });
  body.replaceChildren(...rows);
}

function renderMastery(progress: ProgressRow[]) {
  const list = $("mastery");
  if (!progress.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No structures practised yet";
    list.replaceChildren(li);
    return;
  }

  const sorted = [...progress].sort((a, b) => b.mastery - a.mastery);
  list.replaceChildren(...sorted.map(p => {
    const m = Math.round(p.mastery * 100);
    const li = document.createElement("li");
    li.innerHTML = `<span class="m-name"></span>
      <span class="m-bar"><i style="width:${m}%"></i></span>
      <span class="m-val">${m}% · ${p.attempts} tries</span>`;
    li.querySelector(".m-name")!.textContent = structName(p.structure_id);
    return li;
  }));
}

function renderHistory(history: HistoryRow[]) {
  const body = $("history-body");
  if (!history.length) {
    showEmpty(body, 5, "No answers yet");
    return;
  }
  body.replaceChildren(...history.map(h => {
    // the backend sends naive UTC timestamps
    const when = new Date(h.at.endsWith("Z") ? h.at : `${h.at}Z`);
    const result = h.correct ? cell("✓ Correct", "ok") : cell("✗ Wrong", "warn");
    return row(cell(when.toLocaleString()), cell(h.lesson_title), cell(h.prompt), cell(h.answer), result);
  }));
}

async function load() {
  const back = new URLSearchParams(LESSON ? { lesson: LESSON } : {});
  $("back-link").setAttribute("href", `/?${back}`);

  let history: HistoryRow[];
  let progress: ProgressRow[];
  try {
    history = await getJSON<HistoryRow[]>(`${API}/api/v1/history/${encodeURIComponent(USER)}`);
    progress = await getJSON<ProgressRow[]>(`${API}/api/v1/progress/${encodeURIComponent(USER)}`);
  } catch (e) {
    $("results-status").textContent = `Could not load results (${errorText(e)})`;
    $("results-status").className = "warn";
    return;
  }

  renderTotals(history);
  renderLessons(history);
  renderMastery(progress);
  renderHistory(history);
}

mountUserBadge(session);
load();
