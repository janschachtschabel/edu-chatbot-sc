import { defineConfig, devices } from '@playwright/test';

/**
 * E2E runner for the built widget bundle (spec §5.5). No `webServer`: the
 * harness serves both the host page and the backend through Playwright's
 * request interception (see e2e/fixtures/harness.ts), so the suite needs
 * nothing but `npm run build:widget` beforehand.
 *
 * Chromium only — the widget ships one bundle for evergreen browsers, and a
 * second engine would double CI time without covering a different code path.
 * Cross-browser rendering checks stay a live/manual concern.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env['CI'],
  retries: 0,
  reporter: process.env['CI'] ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'https://host.test',
    trace: 'retain-on-failure',
    // NOTE: reduced motion is emulated in `mount()`, not here. The
    // `reducedMotion` context option resolves into `project.use` but does not
    // reach the page in Playwright 1.62 (measured: `matchMedia(...).matches`
    // stayed false), while an explicit `page.emulateMedia` works. One visible
    // source of truth in the harness beats config that silently does nothing.
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
