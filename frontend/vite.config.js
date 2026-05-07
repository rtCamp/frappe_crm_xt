import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

// A minimal virtual-module plugin that stubs out ~icons/* imports
// (frappe-ui's Toast uses lucide icons; we don't use Toast so an empty
// component is fine).
function stubIconsPlugin() {
  return {
    name: 'stub-icons',
    resolveId(id) {
      if (id.startsWith('~icons/')) return '\0stub-icon:' + id
    },
    load(id) {
      if (id.startsWith('\0stub-icon:')) {
        // Return an empty Vue functional component
        return 'export default { render() {} }'
      }
    },
  }
}

export default defineConfig({
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  plugins: [stubIconsPlugin(), vue()],
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
      output: {
        inlineDynamicImports: true,
      },
    },
  },
})
