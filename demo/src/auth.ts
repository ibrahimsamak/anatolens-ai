import { API } from "./util";

const SESSION_KEY = "anatolens.session";

export type Role = "SUPER_ADMIN" | "CONTENT_EDITOR" | "MEDICAL_REVIEWER" | "TEACHER" | "STUDENT";
export type User = { id: string; email: string; role: Role; display_name: string };
export type Session = { access_token: string; refresh_token: string; user: User };

export const STAFF: Role[] = ["SUPER_ADMIN", "CONTENT_EDITOR", "MEDICAL_REVIEWER"];

export const ROLE_LABEL: Record<Role, string> = {
  SUPER_ADMIN: "Admin",
  CONTENT_EDITOR: "Content editor",
  MEDICAL_REVIEWER: "Medical reviewer",
  TEACHER: "Teacher",
  STUDENT: "Student",
};


export function getSession(): Session | null {
  try {
    const session: Session | null = JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null");
    if (!session || isExpired(session.refresh_token)) return null;
    return session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch { }
}

export function clearSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch { }
}

function isExpired(token: string): boolean {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload));
    return typeof exp !== "number" || exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function goToLogin() {
  const next = location.pathname + location.search;
  location.href = `/login.html?${new URLSearchParams({ next })}`;
}

export function logout() {
  clearSession();
  location.href = "/login.html";
}

export function requireSession(roles?: Role[]): Session {
  const session = getSession();
  if (!session) {
    goToLogin();
    throw new Error("not signed in");
  }
  if (roles && !roles.includes(session.user.role)) {
    location.href = "/";
    throw new Error("role not allowed");
  }
  return session;
}

async function refreshSession(session: Session): Promise<Session | null> {
  const res = await fetch(`${API}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refresh_token }),
  });
  if (!res.ok) return null;

  const fresh: Session = await res.json();
  saveSession(fresh);
  return fresh;
}

export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  let session = getSession();
  if (!session) {
    goToLogin();
    throw new Error("not signed in");
  }

  const send = (token: string) =>
    fetch(url, { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } });

  let res = await send(session.access_token);
  if (res.status !== 401) return res;

  session = await refreshSession(session);
  if (!session) {
    clearSession();
    goToLogin();
    throw new Error("session expired");
  }
  return send(session.access_token);
}

export function mountUserBadge(session: Session) {
  const actions = document.querySelector(".actions");
  if (!actions) return;

  const name = document.createElement("span");
  name.className = "u-name";
  name.textContent = session.user.display_name;

  const role = document.createElement("span");
  role.className = "u-role";
  role.textContent = ROLE_LABEL[session.user.role] ?? session.user.role;

  const badge = document.createElement("span");
  badge.id = "user-badge";
  badge.className = "user-badge";
  badge.append(name, role);

  const signOut = document.createElement("button");
  signOut.type = "button";
  signOut.id = "logout-btn";
  signOut.textContent = "Sign out";
  signOut.onclick = logout;

  actions.append(badge, signOut);
}
