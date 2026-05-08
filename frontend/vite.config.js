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

// Stub out vue-router so frappe-ui's Button (which optionally uses RouterLink)
// bundles cleanly as an IIFE.  We run inside FCRM which owns the real router;
// we never call router APIs ourselves, so a no-op shim is sufficient.
function stubVueRouterPlugin() {
  const STUB_ID = '\0stub-vue-router'
  return {
    name: 'stub-vue-router',
    resolveId(id) {
      if (id === 'vue-router') return STUB_ID
    },
    load(id) {
      if (id === STUB_ID) {
        // Export the handful of symbols frappe-ui actually imports
        return `
export const RouterLink = { render() {} }
export const RouterView = { render() {} }
export function useRouter() { return null }
export function useRoute() { return null }
export function useLink() { return {} }
`
      }
    },
  }
}

export default defineConfig({
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  plugins: [stubIconsPlugin(), stubVueRouterPlugin(), vue()],
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
