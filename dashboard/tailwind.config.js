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
          bg: '#FFFBF5',
          card: '#FFFFFF',
          primary: '#FF4D6D',
          secondary: '#7C3AED',
          accent: '#FBBF24',
          success: '#10B981',
          info: '#3B82F6',
          warning: '#F59E0B',
          text: '#1A1A2E',
          muted: '#6B7280',
          border: '#E5E7EB',
        },
        dark: {
          bg: '#0B0F1A',
          card: '#151B2B',
          primary: '#FF4D6D',
          secondary: '#A78BFA',
          accent: '#FBBF24',
          success: '#34D399',
          info: '#60A5FA',
          warning: '#FBBF24',
          text: '#F1F5F9',
          muted: '#94A3B8',
          border: '#2D2D44',
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
        'orbit': 'orbit 20s linear infinite',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'blob-morph': 'blobMorph 8s ease-in-out infinite',
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
        orbit: {
          '0%': { transform: 'rotate(0deg) translateX(var(--orbit-radius)) rotate(0deg)' },
          '100%': { transform: 'rotate(360deg) translateX(var(--orbit-radius)) rotate(-360deg)' },
        },
        glowPulse: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 20px rgba(255, 77, 109, 0.4)' },
          '50%': { opacity: '0.8', boxShadow: '0 0 40px rgba(255, 77, 109, 0.7)' },
        },
        blobMorph: {
          '0%, 100%': { borderRadius: '60% 40% 30% 70% / 60% 30% 70% 40%' },
          '25%': { borderRadius: '30% 60% 70% 40% / 50% 60% 30% 60%' },
          '50%': { borderRadius: '50% 60% 30% 60% / 30% 60% 70% 40%' },
          '75%': { borderRadius: '60% 40% 60% 30% / 70% 30% 50% 60%' },
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
        'glow-pink': '0 0 20px rgba(255, 77, 109, 0.4)',
        'glow-purple': '0 0 20px rgba(124, 58, 237, 0.4)',
        'glow-gold': '0 0 20px rgba(251, 191, 36, 0.4)',
        'glow-emerald': '0 0 20px rgba(16, 185, 129, 0.4)',
        'glow-blue': '0 0 20px rgba(59, 130, 246, 0.4)',
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #FF4D6D, #7C3AED)',
        'gradient-warm': 'linear-gradient(135deg, #FF4D6D, #FBBF24)',
        'gradient-cool': 'linear-gradient(135deg, #7C3AED, #3B82F6)',
        'gradient-aurora': 'linear-gradient(135deg, #FF4D6D, #7C3AED, #3B82F6, #10B981, #FBBF24)',
      },
    },
  },
  plugins: [],
};
