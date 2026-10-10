import { defineConfig } from "@playwright/test";

const API_PORT = 8010;
const WEB_PORT = 3110;

export default defineConfig({
  testDir: "../tests/e2e",
  timeout: 90_000,
  use: { baseURL: `http://localhost:${WEB_PORT}`, viewport: { width: 1440, height: 900 } },
  webServer: [
    {
      command: `uv run uvicorn backend.main:app --port ${API_PORT}`,
      cwd: "..",
      url: `http://localhost:${API_PORT}/healthz`,
      env: {
        DATABASE_URL: "sqlite:///data/e2e.db",
        REPLAY_DIR: "data/e2e-replays",
        CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `pnpm exec next dev -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      env: { NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
