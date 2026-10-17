import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  use: {
    baseURL: "http://localhost:5173",
    channel: process.env.PW_CHANNEL || undefined,
  },
  webServer: { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true },
});
