import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:48765', channel: 'msedge', viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 },
  webServer: { command: 'uv run --project .. python -B ../tests/serve_browser.py', url: 'http://127.0.0.1:48765', reuseExistingServer: false, timeout: 30000 },
});
