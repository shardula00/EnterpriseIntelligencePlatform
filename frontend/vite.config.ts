/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Every mocked module's call history resets between tests, so one
    // test's calls to a mocked API function can never leak into the next.
    clearMocks: true,
    // Phase 12: coverage is measured and reported (`npm run test:coverage`),
    // not gated at a hard percentage - see SECURITY.md for why. `schema.d.ts`
    // is generated output (openapi-typescript), not hand-written code, and
    // `main.tsx`/`vite-env.d.ts` are framework bootstrap with no branches of
    // their own worth measuring.
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/api/schema.d.ts',
        'src/main.tsx',
        'src/vite-env.d.ts',
        '**/*.test.{ts,tsx}',
        'src/test/**',
      ],
    },
  },
})
