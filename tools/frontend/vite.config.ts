import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { viteSingleFile } from 'vite-plugin-singlefile';
import path from 'path';
import fs from 'fs';

function renameToUiWorkbench() {
  return {
    name: 'rename-to-ui-workbench',
    closeBundle() {
      const src = path.resolve(__dirname, 'dist/index.html');
      const dest = path.resolve(__dirname, '../ui_workbench.html');
      if (fs.existsSync(src)) {
        fs.copyFileSync(src, dest);
        console.log(`[Workbench] Successfully built single-file bundle: ${dest}`);
      }
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    viteSingleFile(),
    renameToUiWorkbench(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'esnext',
    cssCodeSplit: false,
  },
});
