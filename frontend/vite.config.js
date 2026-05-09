import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://web:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  resolve: {
    alias: [
      {
        find: /^leaflet-draw$/,
        replacement: path.resolve(__dirname, './src/leaflet-draw-shim.js')
      }
    ],
  },
  optimizeDeps: {
    include: ['react-leaflet-draw'],
  }
})
