import { test, expect, type Page } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

async function mockBackend(page: Page) {
  await page.route(`${API}/lessons/spine_001`, r => r.fulfill({ json: {
    id: "spine_001", title: "Vertebral Column", model_url: "/assets/spine.glb", ios_model_url: "/assets/spine.usdz" } }));
  await page.route(`${API}/lessons/spine_001/structures`, r => r.fulfill({ json: [
    { id: "spine.lumbar_region", mesh_name: "Spine_Lumbar", name_en: "Lumbar region (L1-L5)", name_ar: null },
    { id: "spine.sacral_region", mesh_name: "Spine_Sacral", name_en: "Sacrum (S1-S5)", name_ar: null } ] }));
  await page.route(`${API}/tutor/ask**`, r => r.fulfill({
    contentType: "text/event-stream",
    body: 'data: {"token": "The lumbar vertebrae "}\r\n\r\n' +
          'data: {"token": "<b>bear weight</b> [1]"}\r\n\r\n' +
          'data: {"done": true, "citations": ["Gray\'s Anatomy"], "grounded": true}\r\n\r\n' }));
}

test("loads spine and explains lumbar (mocked API)", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  await expect(page.locator("#lesson-title")).toContainText("Vertebral Column");
  await expect(page.locator('.hotspot[data-sid="spine.lumbar_region"]')).toHaveAttribute("data-position", /m/);
  await page.locator("#panel").getByRole("button", { name: /Lumbar/i }).click();
  await expect(page.locator("#card")).toContainText(/lumbar/i);
  await expect(page.locator("#card-meta")).toContainText("Gray's Anatomy");
  await expect(page.locator("#card-text b")).toHaveCount(0);
});

test("content plugin serves the lesson GLB", async ({ request }) => {
  const r = await request.get("/assets/spine.glb");
  expect(r.ok()).toBeTruthy();
  expect((await r.body()).subarray(0, 4).toString()).toBe("glTF");
});

test("shows a clear error when the backend is down", async ({ page }) => {
  await page.route(`${API}/**`, r => r.abort());
  await page.goto("/");
  await expect(page.locator("#lesson-status")).toContainText(/Backend unavailable/);
});

test("e2e: real backend explains lumbar", async ({ page }) => {
  test.skip(!process.env.E2E, "set E2E=1 with the backend running");
  await page.goto("/");
  await page.getByRole("button", { name: /Lumbar/i }).first().click();
  await expect(page.locator("#card-text")).toContainText(/lumbar/i, { timeout: 30_000 });
});
