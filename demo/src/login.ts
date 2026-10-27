import { getSession, saveSession, ROLE_LABEL, STAFF, type Role, type Session } from "./auth";

const API: string = import.meta.env.VITE_API ?? "";
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

// Mirrors backend/app/seed_users.py (dev/demo only).
const DEMO_PASSWORD = "demo1234";
const DEMO: { email: string; role: Role; name: string }[] = [
  { email: "admin@anatolens.dev", role: "SUPER_ADMIN", name: "Sara Admin" },
  { email: "editor@anatolens.dev", role: "CONTENT_EDITOR", name: "Karim Editor" },
  { email: "reviewer@anatolens.dev", role: "MEDICAL_REVIEWER", name: "Dr. Nadia Reviewer" },
  { email: "teacher@anatolens.dev", role: "TEACHER", name: "Youssef Teacher" },
  { email: "amira@anatolens.dev", role: "STUDENT", name: "Amira" },
  { email: "omar@anatolens.dev", role: "STUDENT", name: "Omar" },
  { email: "lina@anatolens.dev", role: "STUDENT", name: "Lina" },
];

// only follow same-site paths so ?next= can't bounce the user to another origin
function destination(s: Session): string {
  const next = new URLSearchParams(location.search).get("next") ?? "";
  if (next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login.html")) return next;
  return STAFF.includes(s.user.role) ? "/review.html" : "/";
}

function setStatus(text: string, cls = "") {
  const s = $("login-status");
  s.textContent = text;
  s.className = cls;
}

async function signIn(email: string, password: string) {
  const submit = $<HTMLButtonElement>("login-submit");
  submit.disabled = true;
  setStatus("Signing in…");
  try {
    const r = await fetch(`${API}/api/v1/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
    });
    if (r.status === 401) throw new Error("Wrong email or password.");
    if (r.status === 422) throw new Error("Enter a valid email address.");
    if (!r.ok) throw new Error(`Sign-in failed (${r.status} ${r.statusText})`);
    const s: Session = await r.json();
    saveSession(s);
    setStatus(`Welcome, ${s.user.display_name}`, "ok");
    location.href = destination(s);
  } catch (e) {
    const msg = e instanceof TypeError ? "Backend unavailable. Is the API running?" : (e as Error).message;
    setStatus(msg, "error");
    submit.disabled = false;
  }
}

$<HTMLFormElement>("login-form").onsubmit = e => {
  e.preventDefault();
  const email = $<HTMLInputElement>("email").value.trim(), password = $<HTMLInputElement>("password").value;
  if (!email || !password) { setStatus("Enter your email and password.", "error"); return; }
  signIn(email, password);
};

$("demo-list").replaceChildren(...DEMO.map(d => {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "demo-account";
  b.innerHTML = `<b></b><small></small>`;
  b.querySelector("b")!.textContent = d.name;
  b.querySelector("small")!.textContent = `${ROLE_LABEL[d.role]} · ${d.email}`;
  b.onclick = () => {
    $<HTMLInputElement>("email").value = d.email;
    $<HTMLInputElement>("password").value = DEMO_PASSWORD;
    signIn(d.email, DEMO_PASSWORD);
  };
  return b;
}));

const existing = getSession();
if (existing) setStatus(`Signed in as ${existing.user.display_name}. Sign in again to switch account.`);
