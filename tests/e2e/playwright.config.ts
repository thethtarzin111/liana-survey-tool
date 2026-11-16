import { defineConfig, devices } from '@playwright/test';

// Runs against the native development stack (admin app on :4200).
export default defineConfig({
  testDir: './specs',
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:4200',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop-1440', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'desktop-1280', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
  ],
});
