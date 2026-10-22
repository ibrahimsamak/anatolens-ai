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

test("adaptive quiz: answer, see feedback + progress, get next question (mocked API)", async ({ page }) => {
  await mockBackend(page);
  let n = 0;
  await page.route(`${API}/quiz/next`, r => {
    n++;
    r.fulfill({ json: { id: `q${n}`, prompt: n === 1 ? "How many <i>lumbar</i> vertebrae?" : "Second question?",
      choices: ["3", "4", "5", "6"], difficulty: n === 1 ? "easy" : "medium", structure_id: "spine.lumbar_region" } });
  });
  await page.route(`${API}/quiz/submit`, async r => {
    const body = r.request().postDataJSON();
    r.fulfill({ json: { correct: body.answer === "5", mastery: 0.3, reward: 1 } });
  });
  await page.route(`${API}/progress/**`, r => r.fulfill({ json: [
    { structure_id: "spine.lumbar_region", mastery: 0.3, attempts: 1 } ] }));

  await page.goto("/");
  await page.getByRole("button", { name: "Quiz me" }).click();
  await expect(page.locator("#quiz-meta")).toContainText(/easy/i);
  await expect(page.locator("#quiz-prompt")).toContainText("<i>lumbar</i>");
  await page.locator("#quiz-choices").getByRole("button", { name: "5" }).click();
  await expect(page.locator("#quiz-feedback")).toHaveText("Correct!");
  await expect(page.locator("#quiz-progress")).toContainText("30%");
  await page.getByRole("button", { name: "Next question" }).click();
  await expect(page.locator("#quiz-prompt")).toHaveText("Second question?");
  await expect(page.locator("#quiz-meta")).toContainText(/medium/i);
});

test("quiz shows an error when no question is available", async ({ page }) => {
  await mockBackend(page);
  await page.route(`${API}/quiz/next`, r => r.fulfill({ status: 404, json: { detail: "no approved questions available" } }));
  await page.goto("/");
  await page.getByRole("button", { name: "Quiz me" }).click();
  await expect(page.locator("#quiz-meta")).toContainText(/Could not load a question/);
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

async function pointOnPart(page: Page, material: string) {
  await page.waitForFunction(() => (document.getElementById("mv") as any)?.loaded === true, null, { timeout: 30_000 });
  return page.evaluate(m => {
    const mv = document.getElementById("mv") as any, r = mv.getBoundingClientRect();
    for (let y = r.top + 4; y < r.bottom; y += 6)
      for (let x = r.left + 4; x < r.right; x += 6)
        if (mv.materialFromPoint(x, y)?.name === m && !(document.elementFromPoint(x, y) as HTMLElement)?.closest(".hotspot"))
          return { x, y };
    return null;
  }, material);
}

test("clicking the bone itself selects it, shows its label and highlights it (mocked API)", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  const p = await pointOnPart(page, "Spine_Lumbar_mat");
  expect(p, "lumbar region should be visible on the model").not.toBeNull();
  await page.mouse.click(p!.x, p!.y);
  await expect(page.locator("#card-title")).toHaveText("Lumbar region (L1-L5)");
  await expect(page.locator('.hotspot[data-sid="spine.lumbar_region"]')).toHaveAttribute("aria-pressed", "true");
  const glow = await page.evaluate(() => Object.fromEntries((document.getElementById("mv") as any).model.materials
    .map((m: any) => [m.name, m.emissiveFactor.some((v: number) => v > 0)])));
  expect(glow["Spine_Lumbar_mat"]).toBe(true);
  expect(glow["Spine_Sacral_mat"]).toBe(false);
});

test("dragging to rotate the model does not select a part", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  const p = await pointOnPart(page, "Spine_Lumbar_mat");
  await page.mouse.move(p!.x, p!.y);
  await page.mouse.down();
  await page.mouse.move(p!.x + 80, p!.y, { steps: 5 });
  await page.mouse.up();
  await expect(page.locator("#card")).toBeHidden();
});
