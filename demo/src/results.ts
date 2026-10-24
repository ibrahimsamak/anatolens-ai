const API: string = import.meta.env.VITE_API ?? "";
const params = new URLSearchParams(location.search);
const USER = params.get("user") ?? "demo-user";
const LESSON = params.get("lesson");

type HistoryRow = { at: string; lesson_id: string; lesson_title: string; structure_id: string;
                    difficulty: string; prompt: string; answer: string; correct: boolean };
type ProgressRow = { structure_id: string; mastery: number; attempts: number };

const $ = (id: string) => document.getElementById(id)!;

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function grade(pct: number): string {
  if (pct >= 90) return "A";
  if (pct >= 80) return "B";
  if (pct >= 70) return "C";
  if (pct >= 60) return "D";
  return "F";
}

const structName = (id: string) => id.split(".").pop()!.replace(/_/g, " ");

function cell(text: string, cls = ""): HTMLTableCellElement {
  const td = document.createElement("td");
  td.textContent = text;
  if (cls) td.className = cls;
  return td;
}

function emptyRow(body: HTMLElement, cols: number, text: string) {
  const tr = document.createElement("tr");
  const td = cell(text, "empty");
  td.colSpan = cols;
  tr.appendChild(td);
  body.replaceChildren(tr);
}

async function load() {
  const qs = new URLSearchParams({ user: USER, ...(LESSON ? { lesson: LESSON } : {}) });
  $("back-link").setAttribute("href", `/?${qs}`);
  let history: HistoryRow[], progress: ProgressRow[];
  try {
    [history, progress] = await Promise.all([
      getJSON<HistoryRow[]>(`${API}/api/v1/history/${encodeURIComponent(USER)}`),
      getJSON<ProgressRow[]>(`${API}/api/v1/progress/${encodeURIComponent(USER)}`),
    ]);
  } catch (e) {
    $("results-status").textContent = `Could not load results (${(e as Error).message})`;
    $("results-status").className = "warn";
    return;
  }

  const correct = history.filter(h => h.correct).length;
  const pct = history.length ? Math.round((correct / history.length) * 100) : 0;
  $("results-status").textContent = history.length
    ? `Results for ${USER}`
    : `No quiz answers yet for ${USER}. Open a lesson and press “Quiz me”.`;
  $("t-grade").textContent = history.length ? grade(pct) : "–";
  $("t-score").textContent = history.length ? `${pct}%` : "–";
  $("t-correct").textContent = String(correct);
  $("t-total").textContent = String(history.length);

  const byLesson = new Map<string, { title: string; total: number; correct: number }>();
  for (const h of history) {
    const l = byLesson.get(h.lesson_id) ?? { title: h.lesson_title, total: 0, correct: 0 };
    l.total++;
    if (h.correct) l.correct++;
    byLesson.set(h.lesson_id, l);
  }
  const lessonsBody = $("lessons-body");
  if (!byLesson.size) emptyRow(lessonsBody, 5, "No lessons quizzed yet");
  else lessonsBody.replaceChildren(...[...byLesson.values()].map(l => {
    const p = Math.round((l.correct / l.total) * 100);
    const tr = document.createElement("tr");
    tr.append(cell(l.title), cell(String(l.total), "num"), cell(String(l.correct), "num"),
              cell(`${p}%`, "num"), cell(grade(p), `grade grade-${grade(p)}`));
    return tr;
  }));

  const mastery = $("mastery");
  if (!progress.length) mastery.replaceChildren(Object.assign(document.createElement("li"), { textContent: "No structures practised yet", className: "empty" }));
  else mastery.replaceChildren(...[...progress].sort((a, b) => b.mastery - a.mastery).map(p => {
    const li = document.createElement("li");
    const m = Math.round(p.mastery * 100);
    li.innerHTML = `<span class="m-name"></span><span class="m-bar"><i style="width:${m}%"></i></span><span class="m-val">${m}% · ${p.attempts} tries</span>`;
    li.querySelector(".m-name")!.textContent = structName(p.structure_id);
    return li;
  }));

  const historyBody = $("history-body");
  if (!history.length) emptyRow(historyBody, 5, "No answers yet");
  else historyBody.replaceChildren(...history.map(h => {
    const tr = document.createElement("tr");
    const when = new Date(h.at.endsWith("Z") ? h.at : `${h.at}Z`);
    tr.append(cell(when.toLocaleString()), cell(h.lesson_title), cell(h.prompt), cell(h.answer),
              cell(h.correct ? "✓ Correct" : "✗ Wrong", h.correct ? "ok" : "warn"));
    return tr;
  }));
}

load();
