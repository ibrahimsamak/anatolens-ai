import type { Page } from "@playwright/test";

export type Role = "SUPER_ADMIN" | "CONTENT_EDITOR" | "MEDICAL_REVIEWER" | "TEACHER" | "STUDENT";

const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");
/** An unsigned JWT-shaped token: the demo only reads `exp`; the (mocked) backend is what verifies signatures. */
export const fakeToken = (role: Role, ttl = 3600) =>
  `${b64({ alg: "HS256" })}.${b64({ sub: "u1", role, exp: Math.floor(Date.now() / 1000) + ttl })}.sig`;

export function session(role: Role = "STUDENT", name = "Amira (student)") {
  return { access_token: fakeToken(role), refresh_token: fakeToken(role),
           user: { id: `demo-${role.toLowerCase()}`, email: "x@anatolens.dev", role, display_name: name } };
}

export async function signedIn(page: Page, role: Role = "STUDENT", name?: string) {
  const s = session(role, name);
  // seed once per tab, so a later sign-out isn't undone by the next navigation
  await page.addInitScript(v => {
    if (sessionStorage.getItem("pw-seeded")) return;
    sessionStorage.setItem("pw-seeded", "1");
    localStorage.setItem("anatolens.session", v);
  }, JSON.stringify(s));
  return s;
}
