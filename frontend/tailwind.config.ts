import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      brand: {
        50: '#EEF1F8',
        100: '#D8DFEF',
        200: '#B1BFDF',
        500: '#35488A',
        600: '#273672',
        DEFAULT: '#1E2A5E',
        700: '#1E2A5E',
        800: '#161F47',
        900: '#0F1633',
      },
      accent: {
        50: '#EAF7F5',
        100: '#CBECE7',
        200: '#99DBD1',
        500: '#14B39D',
        DEFAULT: '#0F9D8A',
        600: '#0F9D8A',
        700: '#0B7D6E',
        800: '#085E53',
      },
      neutral: {
        0: '#FFFFFF',
        white: '#FFFFFF',
        50: '#F5F7FA',
        surface: '#F5F7FA',
        200: '#E3E8EF',
        border: '#E3E8EF',
        500: '#64748B',
        muted: '#64748B',
        900: '#0F172A',
        ink: '#0F172A',
      },
    },
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '8px',
        md: '8px',
        lg: '8px',
      },
    },
  },
  plugins: [],
};

export default config;
