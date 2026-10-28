import { test, expect, type Page } from "@playwright/test";
import { session, signedIn, type Role } from "./session";

const API = "**/api/v1";

async function mockLessons(page: Page) {
  await page.route(`${API}/lessons`, r => r.fulfill({ json: [{ id: "spine_001", title: "Vertebral Column", system: "skeletal" }] }));
  await page.route(`${API}/lessons/spine_001`, r => r.fulfill({ json: {
    id: "spine_001", title: "Vertebral Column", model_url: "/assets/spine.glb", ios_model_url: null } }));
  await page.route(`${API}/lessons/spine_001/structures`, r => r.fulfill({ json: [
    { id: "spine.lumbar_region", mesh_name: "Spine_Lumbar", name_en: "Lumbar region (L1-L5)", name_ar: null } ] }));
}

test.beforeEach(async ({ page }) => {
  await page.route(`${API}/admin/proposals**`, r => r.fulfill({ json: [] }));
  await page.route(`${API}/admin/meshes**`, r => r.fulfill({ json: [] }));
});

async function mockLogin(page: Page) {
  await page.route(`${API}/auth/login`, r => {
    const { email, password } = r.request().postDataJSON();
    if (password !== "demo1234") return r.fulfill({ status: 401, json: { detail: "invalid email or password" } });
    const role: Role = email.startsWith("reviewer") ? "MEDICAL_REVIEWER" : email.startsWith("editor") ? "CONTENT_EDITOR" : "STUDENT";
    r.fulfill({ json: session(role, email.split("@")[0]) });
  });
}

const PENDING = { thread_id: "spine_001:spine.lumbar_region:ab12", lesson_id: "spine_001", structure_id: "spine.lumbar_region",
  status: "MEDICAL_REVIEW", draft_text: "The lumbar region has five vertebrae.", created_by: "editor@anatolens.dev",
  reviewer: null, notes: null, updated_at: "2026-10-27T10:00:00" };

test("signed-out visitor is sent to the login screen", async ({ page }) => {
  await page.goto("/?lesson=spine_001");
  await expect(page).toHaveURL(/\/login\.html\?next=/);
  await expect(page.getByRole("heading", { name: "AnatoLens" })).toBeVisible();
});

test("student signs in and lands on the lesson with their name in the header", async ({ page }) => {
  await mockLogin(page);
  await mockLessons(page);
  await page.goto("/login.html?next=%2F%3Flesson%3Dspine_001");
  await page.getByLabel("Email").fill("amira@anatolens.dev");
  await page.getByLabel("Password").fill("demo1234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/\?lesson=spine_001$/);
  await expect(page.locator("#user-badge")).toContainText("amira");
  await expect(page.locator("#user-badge")).toContainText("Student");
  await expect(page.locator("#review-link")).toBeHidden();
});

test("wrong password shows an error and stays on the login screen", async ({ page }) => {
  await mockLogin(page);
  await page.goto("/login.html");
  await page.getByLabel("Email").fill("amira@anatolens.dev");
  await page.getByLabel("Password").fill("nope");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#login-status")).toHaveText("Wrong email or password.");
  await expect(page).toHaveURL(/login\.html/);
});

test("next= pointing at another site is ignored", async ({ page }) => {
  await mockLogin(page);
  await mockLessons(page);
  await page.goto("/login.html?next=//evil.example/");
  await page.getByLabel("Email").fill("amira@anatolens.dev");
  await page.getByLabel("Password").fill("demo1234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("http://localhost:5173/");
});

test("demo reviewer account opens the review queue and can approve", async ({ page }) => {
  await mockLogin(page);
  let queue = [PENDING];
  await page.route(`${API}/admin/reviews**`, r => r.fulfill({ json: queue }));
  let decided: unknown = null;
  await page.route(`${API}/admin/review/**`, r => {
    decided = r.request().postDataJSON();
    queue = [];
    r.fulfill({ json: { ...PENDING, status: "APPROVED" } });
  });
  await page.goto("/login.html");
  await page.getByRole("button", { name: /Dr\. Nadia Reviewer/ }).click();
  await expect(page).toHaveURL(/review\.html/);
  await expect(page.locator("#author-box")).toBeHidden();   // reviewers don't author
  await expect(page.locator(".review-card")).toContainText("five vertebrae");
  await page.getByLabel("Review notes").fill("looks right");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("#review-status")).toHaveText("Nothing here yet.");
  expect(decided).toEqual({ decision: "approve", notes: "looks right" });
});

test("editor sees the authoring box but cannot approve", async ({ page }) => {
  await signedIn(page, "CONTENT_EDITOR", "Karim Editor");
  await mockLessons(page);
  await page.route(`${API}/admin/reviews**`, r => r.fulfill({ json: [PENDING] }));
  await page.goto("/review.html");
  await expect(page.locator("#author-box")).toBeVisible();
  await expect(page.locator("#author-structure")).toHaveValue("spine.lumbar_region");
  await expect(page.locator(".review-card")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
});

const PROPOSAL = { id: "p1", lesson_id: "spine_001", subject_id: "spine.lumbar_region", predicate: "part_of",
  object_id: "spine.cervical_region", confidence: 0.6, status: "AI_GENERATED", conflict: true };

test("reviewer sees a conflicting AI link and can reject it", async ({ page }) => {
  await signedIn(page, "MEDICAL_REVIEWER", "Dr. Nadia Reviewer");
  await page.route(`${API}/admin/reviews**`, r => r.fulfill({ json: [] }));
  let proposals = [PROPOSAL];
  await page.route(`${API}/admin/proposals**`, r => r.fulfill({ json: proposals }));
  let decided = "";
  await page.route(`${API}/admin/proposals/p1/*`, r => {
    decided = r.request().url().split("/").pop()!;
    proposals = [];
    r.fulfill({ json: { ...PROPOSAL, status: "DRAFT" } });
  });
  await page.goto("/review.html");
  await expect(page.locator("#analyze-box")).toBeHidden();
  const card = page.locator("#suggest-list .review-card");
  await expect(card).toContainText("lumbar region → part of → cervical region");
  await expect(card).toContainText("Contradicts approved anatomy");
  await card.getByRole("button", { name: "Reject" }).click();
  await expect(page.locator("#suggest-status")).toHaveText("Nothing here yet.");
  expect(decided).toBe("reject");
});

test("editor analyzes a diagram and sees the summary", async ({ page }) => {
  await signedIn(page, "CONTENT_EDITOR", "Karim Editor");
  await mockLessons(page);
  await page.route(`${API}/admin/reviews**`, r => r.fulfill({ json: [] }));
  await page.route(`${API}/admin/lessons/spine_001/analyze**`, r => r.fulfill({ status: 201, json: {
    regions: [{ label: "Lumbar", structure_id: "spine.lumbar_region" }], proposals: [PROPOSAL], mesh: null,
    known: [{ subject_id: "spine.sacral_region", predicate: "connects_to", object_id: "spine.coccygeal_region" }],
    notes: ["3D skipped: transformers is not installed"] } }));
  await page.goto("/review.html");
  await expect(page.locator("#analyze-btn")).toBeDisabled();
  await page.locator("#analyze-file").setInputFiles({ name: "d.png", mimeType: "image/png", buffer: Buffer.from("png") });
  await page.locator("#analyze-btn").click();
  await expect(page.locator("#analyze-status")).toContainText("Found parts: lumbar region");
  await expect(page.locator("#analyze-status")).toContainText("Found 2 link(s): 1 new sent for review, 1 already known");
  await expect(page.locator("#suggest-list .review-card")).toHaveCount(0);
});

test("student opening the review page is sent back to the lessons", async ({ page }) => {
  await signedIn(page, "STUDENT");
  await mockLessons(page);
  await page.goto("/review.html");
  await expect(page).toHaveURL("http://localhost:5173/");
});

test("an expired access token is refreshed once, then the request is retried", async ({ page }) => {
  await signedIn(page, "MEDICAL_REVIEWER");
  const fresh = session("MEDICAL_REVIEWER");
  fresh.access_token = "fresh-token";
  await page.route(`${API}/auth/refresh`, r => r.fulfill({ json: fresh }));
  await page.route(`${API}/admin/reviews**`, r =>
    r.request().headers().authorization === "Bearer fresh-token"
      ? r.fulfill({ json: [PENDING] }) : r.fulfill({ status: 401, json: { detail: "invalid token" } }));
  await page.goto("/review.html");
  await expect(page.locator(".review-card")).toBeVisible();
});

test("sign out clears the session and returns to the login screen", async ({ page }) => {
  await signedIn(page, "STUDENT");
  await mockLessons(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/login\.html$/);
  expect(await page.evaluate(() => localStorage.getItem("anatolens.session"))).toBeNull();
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\.html\?next=/);
});
