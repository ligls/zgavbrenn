import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Two builds share this config:
//   npm run build             -> dist/            served by server/server.py (API + SQLite edits)
//   npm run build:standalone  -> dist-standalone/ one inlined index.html (vite build --mode standalone);
//                                importer/build_standalone.py then embeds the dataset so the file
//                                works from file:// with no server.
// In development the Vite dev server proxies /api to Flask (port 8765).
export default defineConfig(({ mode }) => {
  const standalone = mode === 'standalone'
  return {
  plugins: [react(), ...(standalone ? [viteSingleFile({ removeViteModuleLoader: true })] : [])],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
    },
  },
  build: {
    outDir: standalone ? 'dist-standalone' : 'dist',
    emptyOutDir: true,
    // the standalone bundle is large by design (data gets appended afterwards)
    chunkSizeWarningLimit: 1500,
  },
  }
})
