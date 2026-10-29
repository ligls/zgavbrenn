import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Vite dev server proxies /api to the Flask server
// (python3 server/server.py, port 8765). In production Flask serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
