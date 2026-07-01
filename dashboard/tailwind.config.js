/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        light: {
          bg: '#F5F4FA',
          card: '#FFFFFF',
          primary: '#ec133e',
          secondary: '#bd0f32',
          accent: '#f4718b',
          success: '#059669',
          info: '#2563EB',
          warning: '#D97706',
          text: '#1a1a1a',
          muted: '#6B7280',
          border: '#E6E3F0',
        },
        dark: {
          bg: '#0C1844',
          card: '#1A2248',
          primary: '#FF6969',
          secondary: '#FF4757',
          accent: '#D4B896',
          success: '#34D399',
          info: '#60A5FA',
          warning: '#FBBF24',
          text: '#FFF5E1',
          muted: '#8890B0',
          border: '#2A3460',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Poppins', 'system-ui', 'sans-serif'],
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'float-slow': 'float 8s ease-in-out infinite',
        'bounce-slow': 'bounce 3s ease-in-out infinite',
        'spin-slow': 'spin 20s linear infinite',
        'aurora': 'aurora 15s ease-in-out infinite',
        'shimmer': 'shimmer 3s ease-in-out infinite',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-in-right': 'slideInRight 0.4s ease-out',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        aurora: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '25%': { backgroundPosition: '100% 50%' },
          '50%': { backgroundPosition: '100% 100%' },
          '75%': { backgroundPosition: '0% 100%' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(40px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      boxShadow: {
        'glow-red': '0 0 20px rgba(236, 19, 62, 0.4)',
        'glow-navy': '0 0 20px rgba(12, 24, 68, 0.4)',
        'glow-crimson': '0 0 20px rgba(189, 15, 50, 0.4)',
        'glow-emerald': '0 0 20px rgba(16, 185, 129, 0.4)',
        'glow-blue': '0 0 20px rgba(37, 99, 235, 0.4)',
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #ec133e, #bd0f32)',
        'gradient-warm': 'linear-gradient(135deg, #ec133e, #1a1a1a)',
        'gradient-cool': 'linear-gradient(135deg, #bd0f32, #1a1a1a)',
        'gradient-success': 'linear-gradient(135deg, #059669, #2563EB)',
        'gradient-aurora': 'linear-gradient(135deg, #ec133e, #bd0f32, #1a1a1a)',
      },
    },
  },
  plugins: [],
};
