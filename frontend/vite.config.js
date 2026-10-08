import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  return {
    server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } } },
    // Django's collected static files live at /static; Vercel serves dist at /.
    base: command === 'build' && !env.VITE_API_BASE_URL ? '/static/' : '/',
  };
});
