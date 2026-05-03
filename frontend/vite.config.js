import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig({
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  plugins: [vue()],
  build: {
    outDir: resolve(__dirname, '../frappe_crm_xt/public/js'),
    emptyOutDir: false,
    lib: {
      entry: resolve(__dirname, 'src/index.js'),
      name: 'CRMXTApp',
      formats: ['iife'],
      fileName: () => 'crm_xt_app.js',
    },
    rollupOptions: {
      // Vue is bundled in — FCRM's Vue is tree-shaken into its own chunk
      // and not exposed globally, so we cannot rely on window.Vue.
      output: {
        inlineDynamicImports: true,
      },
    },
  },
})
