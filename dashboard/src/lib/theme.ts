export type ThemeMode = 'light' | 'dark';

export const themeConfig = {
  light: {
    background: '#FAFAFA',
    card: '#FFFFFF',
    primary: '#FF6B6B',
    secondary: '#4ECDC4',
    accent: '#FFD93D',
    text: '#1A1A2E',
    textSecondary: '#6B7280',
    border: '#E5E7EB',
    shadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
    gradient: 'linear-gradient(135deg, #FAFAFA 0%, #FFF5F5 50%, #F0FFFE 100%)',
  },
  dark: {
    background: '#0F0F23',
    card: '#1A1A2E',
    primary: '#FF7675',
    secondary: '#00D2FF',
    accent: '#F39C12',
    text: '#F1F5F9',
    textSecondary: '#94A3B8',
    border: '#2D2D44',
    shadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
    gradient: 'linear-gradient(135deg, #0F0F23 0%, #1A1A3E 50%, #0F0F23 100%)',
  },
};

export function toggleTheme(): ThemeMode {
  const current = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.classList.toggle('dark', next === 'dark');
  localStorage.setItem('theme', next);
  return next;
}

export function initTheme(): ThemeMode {
  const saved = localStorage.getItem('theme') as ThemeMode | null;
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.classList.toggle('dark', theme === 'dark');
  return theme;
}
