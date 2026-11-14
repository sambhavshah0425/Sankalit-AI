import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8001',
      '/rag': 'http://127.0.0.1:8001',
      '/documents': 'http://127.0.0.1:8001',
      '/knowledge': 'http://127.0.0.1:8001',
      '/health': 'http://127.0.0.1:8001',
      '/chat': 'http://127.0.0.1:8001',
      '/company': 'http://127.0.0.1:8001',
      '/audit': 'http://127.0.0.1:8001',
    },
  },
})
