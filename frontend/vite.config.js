import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// In development the React app calls /api/... and Vite forwards it to the FastAPI backend.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    build: { chunkSizeWarningLimit: 900 }, // cytoscape is large; fine for a local demo
    server: {
      port: 5173,
      proxy: { '/api': env.VITE_BACKEND_URL || 'http://localhost:8000' },
    },
  }
})
