/// <reference types="vitest" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4200,
    strictPort: true, // fail instead of silently moving to another port
    // `npm run dev` talks to the API running locally on port 8000.
    proxy: { '/api': 'http://127.0.0.1:8000', '/r': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
