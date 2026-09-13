import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Installable PWA: added to a home screen, the app opens full screen like a
// regular app, and the service worker keeps the app shell available offline.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['apple-touch-icon.png', 'favicon-64.png'],
      manifest: {
        name: 'PromptlyHired - Resume & Cover Letter Tailoring',
        short_name: 'PromptlyHired',
        description:
          'Paste a job link, see how you match it, and generate a tailored resume and cover letter.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#0b1220',
        theme_color: '#0b1220',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,svg,woff2}'],
        // Offline shell: any navigation falls back to the cached index.html, so
        // a deep link still boots the app with no network.
        navigateFallback: 'index.html',
        // Only the app shell is precached. API responses are per-user and
        // authenticated, so they are deliberately never cached by the service
        // worker - stale or cross-account data would be worse than a spinner.
        navigateFallbackDenylist: [/^\/api/, /^\/media/],
        runtimeCaching: [],
        cleanupOutdatedCaches: true,
      },
      devOptions: { enabled: false },
    }),
  ],
  server: { port: 5173 },
})
