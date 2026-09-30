import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Backend (FastAPI/uvicorn) runs on :8000; the frontend only ever talks
      // to /api/* (REST + the /api/stream SSE endpoint) via this proxy.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE streams must not be buffered/re-chunked by the proxy.
        ws: false,
      },
    },
  },
})
