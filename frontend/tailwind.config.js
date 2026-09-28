/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Muted, professional palette — deliberately not a bright AI-SaaS gradient theme
        ink: '#1a2332',
        slate: {
          850: '#1e293b',
        },
      },
    },
  },
  plugins: [],
}
