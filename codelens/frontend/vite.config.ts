import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    host: '0.0.0.0',
    allowedHosts: ['codelens-5.onrender.com'],

    proxy: {
      '/api': {
        target: 'https://codelens-2-v0jy.onrender.com',
        changeOrigin: true,
        secure: true
      }
    }
  }
})