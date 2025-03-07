import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // 1) Set base to match your subfolder path
  base: "/aposto-chatbot/",

  // 2) Keep your existing plugins
  plugins: [react(), tailwindcss()],
  build: {
    lib: {
      entry: 'src/main.tsx',
      name: 'Chatbot',
      fileName: (format) => `chatbot.${format}.js`,
    },
    minify: false,
    rollupOptions: {
      output: {
        globals: {
          // react: 'React',
          // 'react-dom': 'ReactDOM',
        },
      },
    },
  },
  define: {
    'process.env': {},
  },
  resolve: {
    alias: {
      process: 'process/browser', // Use process/browser to resolve the process variable
    },
  },
})