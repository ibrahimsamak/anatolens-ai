import { getSession, saveSession, ROLE_LABEL, STAFF, type Role, type Session } from "./auth";
import { $, API } from "./util";

const DEMO_PASSWORD = "demo1234";
const DEMO_ACCOUNTS: { email: string; role: Role; name: string }[] = [
  { email: "admin@anatolens.dev", role: "SUPER_ADMIN", name: "Sara Admin" },
  { email: "editor@anatolens.dev", role: "CONTENT_EDITOR", name: "Karim Editor" },
  { email: "reviewer@anatolens.dev", role: "MEDICAL_REVIEWER", name: "Dr. Nadia Reviewer" },
  { email: "teacher@anatolens.dev", role: "TEACHER", name: "Youssef Teacher" },
  { email: "amira@anatolens.dev", role: "STUDENT", name: "Amira" },
  { email: "omar@anatolens.dev", role: "STUDENT", name: "Omar" },
  { email: "lina@anatolens.dev", role: "STUDENT", name: "Lina" },
];

function setStatus(text: string, cls = "") {
  const el = $("login-status");
  el.textContent = text;
  el.className = cls;
}

function destination(session: Session): string {
  const next = new URLSearchParams(location.search).get("next") ?? "";
  const isLocalPath = next.startsWith("/") && !next.startsWith("//");
  if (isLocalPath && !next.startsWith("/login.html")) return next;
  if (STAFF.includes(session.user.role)) return "/review.html";
  return "/";
}

async function login(email: string, password: string): Promise<Session> {
  let res: Response;
  try {
    res = await fetch(`${API}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new Error("Backend unavailable. Is the API running?");
  }
  if (res.status === 401) throw new Error("Wrong email or password.");
  if (res.status === 422) throw new Error("Enter a valid email address.");
  if (!res.ok) throw new Error(`Sign-in failed (${res.status} ${res.statusText})`);
  return res.json();
}

async function signIn(email: string, password: string) {
  const submit = $<HTMLButtonElement>("login-submit");
  submit.disabled = true;
  setStatus("Signing in…");
  try {
    const session = await login(email, password);
    saveSession(session);
    setStatus(`Welcome, ${session.user.display_name}`, "ok");
    location.href = destination(session);
  } catch (e) {
    setStatus((e as Error).message, "error");
    submit.disabled = false;
  }
}

function demoButton(account: typeof DEMO_ACCOUNTS[number]): HTMLButtonElement {
  const name = document.createElement("b");
  name.textContent = account.name;
  const detail = document.createElement("small");
  detail.textContent = `${ROLE_LABEL[account.role]} · ${account.email}`;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "demo-account";
  btn.append(name, detail);
  btn.onclick = () => {
    $<HTMLInputElement>("email").value = account.email;
    $<HTMLInputElement>("password").value = DEMO_PASSWORD;
    signIn(account.email, DEMO_PASSWORD);
  };
  return btn;
}

$<HTMLFormElement>("login-form").onsubmit = e => {
  e.preventDefault();
  const email = $<HTMLInputElement>("email").value.trim();
  const password = $<HTMLInputElement>("password").value;
  if (!email || !password) {
    setStatus("Enter your email and password.", "error");
    return;
  }
  signIn(email, password);
};

$("demo-list").replaceChildren(...DEMO_ACCOUNTS.map(demoButton));

const current = getSession();
if (current) {
  setStatus(`Signed in as ${current.user.display_name}. Sign in again to switch account.`);
}
