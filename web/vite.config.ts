import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// SPA served by the FastAPI app; every route falls back to index.html
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: { proxy: { '/api': 'http://127.0.0.1:8700' } }
});
