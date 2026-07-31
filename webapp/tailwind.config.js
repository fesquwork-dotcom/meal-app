/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        app: {
          bg: 'var(--app-bg)',
          text: 'var(--app-text)',
          hint: 'var(--app-hint)',
          link: 'var(--app-link)',
          button: 'var(--app-button)',
          'button-text': 'var(--app-button-text)',
          secondary: 'var(--app-secondary)',
          'header-bg': 'var(--app-header-bg)',
          accent: 'var(--app-accent)',
          destructive: 'var(--app-destructive)',
          'destructive-text': 'var(--app-destructive-text)',
          section: 'var(--app-section-bg)',
          'section-header': 'var(--app-section-header)',
          subtitle: 'var(--app-subtitle)',
          'bottom-bar': 'var(--app-bottom-bar)',
        },
      },
      borderRadius: {
        app: 'var(--app-radius)',
        'app-lg': 'var(--app-radius-lg)',
      },
      fontFamily: {
        app: ['var(--app-font)', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
