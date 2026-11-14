import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // maplibre-gl cria seu worker via `new Worker(new URL(...))`; o
  // pré-bundle do esbuild (optimizeDeps) reescreve essa URL de um jeito
  // que quebra em dev ("Worker failed to load") -- excluir do pre-bundle
  // resolve, é o fix documentado da própria comunidade do maplibre-gl.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
