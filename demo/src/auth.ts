const API: string = import.meta.env.VITE_API ?? "";
const KEY = "anatolens.session";

export type Role = "SUPER_ADMIN" | "CONTENT_EDITOR" | "MEDICAL_REVIEWER" | "TEACHER" | "STUDENT";
export type User = { id: string; email: string; role: Role; display_name: string };
export type Session = { access_token: string; refresh_token: string; user: User };

export const STAFF: Role[] = ["SUPER_ADMIN", "CONTENT_EDITOR", "MEDICAL_REVIEWER"];
export const ROLE_LABEL: Record<Role, string> = {
  SUPER_ADMIN: "Admin", CONTENT_EDITOR: "Content editor", MEDICAL_REVIEWER: "Medical reviewer",
  TEACHER: "Teacher", STUDENT: "Student",
};

export function getSession(): Session | null {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) ?? "null") as Session | null;
    return s && !expired(s.refresh_token) ? s : null;
  } catch { return null; }
}

export function saveSession(s: Session) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode: session lasts for this page only */ }
}

export function clearSession() {
  try { localStorage.removeItem(KEY); } catch { }
}

function expired(token: string): boolean {
  try {
    const { exp } = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof exp !== "number" || exp * 1000 <= Date.now();
  } catch { return true; }
}

export function goToLogin() {
  location.href = `/login.html?${new URLSearchParams({ next: location.pathname + location.search })}`;
}

/** The signed-in session, or a redirect to the login screen (and to the lesson page if the role isn't allowed). */
export function requireSession(roles?: Role[]): Session {
  const s = getSession();
  if (!s) { goToLogin(); throw new Error("not signed in"); }
  if (roles && !roles.includes(s.user.role)) { location.href = "/"; throw new Error("role not allowed"); }
  return s;
}

export function logout() {
  clearSession();
  location.href = "/login.html";
}

async function refresh(s: Session): Promise<Session | null> {
  const r = await fetch(`${API}/api/v1/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: s.refresh_token }),
  });
  if (!r.ok) return null;
  const next: Session = await r.json();
  saveSession(next);
  return next;
}

/** fetch with the bearer token; on 401 refreshes once, then sends the user back to the login screen. */
export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  let s = getSession();
  if (!s) { goToLogin(); throw new Error("not signed in"); }
  const send = (tok: string) => fetch(url, { ...init, headers: { ...init.headers, Authorization: `Bearer ${tok}` } });
  let r = await send(s.access_token);
  if (r.status === 401) {
    s = await refresh(s);
    if (!s) { clearSession(); goToLogin(); throw new Error("session expired"); }
    r = await send(s.access_token);
  }
  return r;
}

/** Adds "name · role" and a sign-out button to the header's action bar. */
export function mountUserBadge(s: Session) {
  const actions = document.querySelector(".actions");
  if (!actions) return;
  const badge = document.createElement("span");
  badge.id = "user-badge";
  badge.className = "user-badge";
  badge.innerHTML = `<span class="u-name"></span><span class="u-role"></span>`;
  badge.querySelector(".u-name")!.textContent = s.user.display_name;
  badge.querySelector(".u-role")!.textContent = ROLE_LABEL[s.user.role] ?? s.user.role;
  const out = document.createElement("button");
  out.type = "button";
  out.id = "logout-btn";
  out.textContent = "Sign out";
  out.onclick = logout;
  actions.append(badge, out);
}
