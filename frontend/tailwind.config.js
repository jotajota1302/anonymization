/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#3C83F6",
        "navy-deep": "#0F172A",
        "slate-custom": "#1E293B",
        // Backwards compat aliases
        jira: {
          blue: '#3C83F6',
          'blue-dark': '#2563EB',
          'blue-light': '#DBEAFE',
          nav: '#0F172A',
          text: '#0F172A',
          'text-subtle': '#475569',
          bg: '#F8FAFC',
          card: '#FFFFFF',
          border: '#E2E8F0',
          green: '#10B981',
          yellow: '#F59E0B',
          red: '#EF4444',
          purple: '#8B5CF6',
        },
      },
      fontFamily: {
        display: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        lg: '0.75rem',
        xl: '1rem',
      },
      fontSize: {
        'body': ['14px', '1.5'],
        'body-sm': ['13px', '1.5'],
        'caption': ['12px', '1.4'],
        'label': ['11px', '1.3'],
        'micro': ['10px', '1.2'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
