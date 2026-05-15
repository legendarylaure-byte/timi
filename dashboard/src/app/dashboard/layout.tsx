'use client';

import { useEffect, useState } from 'react';
import { auth } from '@/lib/firebase';
import { onAuthStateChanged, User } from 'firebase/auth';
import { useRouter, usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { NotificationCenter } from '@/components/ui/NotificationCenter';
import { APP_NAME } from '@/lib/constants';
import Image from 'next/image';

const navItems = [
  { label: 'Dashboard', icon: '📊', path: '/dashboard' },
  { label: 'Workspace', icon: '🎬', path: '/dashboard/workspace' },
  { label: 'Archive', icon: '📁', path: '/dashboard/archive' },
  { label: 'Trends', icon: '🔥', path: '/dashboard/trends' },
  { label: 'Repurpose', icon: '✂️', path: '/dashboard/repurpose' },
  { label: 'Preview', icon: '🎨', path: '/dashboard/preview' },
  { label: 'Publishing', icon: '📤', path: '/dashboard/publishing' },
  { label: 'Analytics', icon: '📈', path: '/dashboard/analytics' },
  { label: 'Monetization', icon: '💰', path: '/dashboard/monetization' },
  { label: 'Series', icon: '🎭', path: '/dashboard/series' },
  { label: 'Scheduler', icon: '⏰', path: '/dashboard/scheduler' },
  { label: 'Calendar', icon: '📅', path: '/dashboard/calendar' },
  { label: 'Brand Safety', icon: '🛡️', path: '/dashboard/brand-safety' },
  { label: 'Logs', icon: '📝', path: '/dashboard/logs' },
  { label: 'Settings', icon: '⚙️', path: '/dashboard/settings' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [currentTime, setCurrentTime] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      if (!u) router.push('/login');
      else setUser(u);
    });
    return () => unsubscribe();
  }, [router]);

  const handleLogout = async () => {
    await auth.signOut();
    router.push('/login');
  };

  if (!user) return (
    <div className="flex items-center justify-center min-h-screen bg-light-bg dark:bg-dark-bg">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
        <p className="text-sm text-light-muted dark:text-dark-muted">Loading...</p>
      </div>
    </div>
  );

  const miniStats = [
    { icon: '🎬', value: '3' },
    { icon: '👁️', value: '28K' },
  ];

  return (
    <div className="min-h-screen bg-light-bg dark:bg-dark-bg flex">
      {/* Desktop Sidebar */}
      <motion.aside
        animate={{ width: sidebarOpen ? 260 : 80 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="hidden md:flex h-screen fixed left-0 top-0 glass-strong z-40 flex-col"
      >
        <div className="p-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-10 h-10 rounded-xl overflow-hidden shrink-0 relative hover:scale-105 transition-transform"
          >
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </button>
          {sidebarOpen && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="truncate">
              <h1 className="gradient-text font-bold text-sm">{APP_NAME}</h1>
              <p className="text-xs text-light-muted dark:text-dark-muted">Timi</p>
            </motion.div>
          )}
        </div>

        {/* Mini stats when collapsed */}
        {!sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="px-3 py-2 flex flex-col items-center gap-2"
          >
            {miniStats.map((stat) => (
              <div key={stat.icon} className="flex flex-col items-center text-center">
                <span className="text-xs">{stat.icon}</span>
                <span className="text-[10px] font-bold text-light-primary">{stat.value}</span>
              </div>
            ))}
          </motion.div>
        )}

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.path;
            return (
              <Link
                key={item.path}
                href={item.path}
                className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group ${
                  isActive
                    ? 'text-white font-medium'
                    : 'text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-dark-text'
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="activeNav"
                    className="absolute inset-0 rounded-xl"
                    style={{
                      background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)',
                    }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
                <motion.span
                  className="relative z-10 text-lg shrink-0"
                  whileHover={{ scale: 1.2 }}
                  whileTap={{ scale: 0.9 }}
                >
                  {item.icon}
                </motion.span>
                {sidebarOpen && (
                  <motion.span className="relative z-10 text-sm">{item.label}</motion.span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-light-border/50 dark:border-dark-border/50 space-y-2">
          <div className="flex items-center gap-3 px-3 py-2">
            {user.photoURL && (
              <div className="w-8 h-8 rounded-full relative ring-2 ring-light-primary/30 shrink-0">
                <img src={user.photoURL} alt={user.displayName || 'User avatar'} className="w-full h-full rounded-full object-cover" />
              </div>
            )}
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-light-text dark:text-dark-text truncate">{user.displayName}</p>
                <p className="text-xs text-light-muted dark:text-dark-muted truncate">{user.email}</p>
              </div>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-light-muted dark:text-dark-muted hover:bg-light-primary/10 hover:text-light-primary transition-colors text-sm"
          >
            <span className="text-lg shrink-0">🚪</span>
            {sidebarOpen && <span>Sign Out</span>}
          </button>
        </div>
      </motion.aside>

      {/* Mobile Bottom Navigation */}
      {isMobile && (
        <motion.nav
          initial={{ y: 100 }}
          animate={{ y: 0 }}
          className="md:hidden fixed bottom-0 left-0 right-0 glass-strong z-50 border-t border-light-border/50 dark:border-dark-border/50"
        >
          <div className="flex items-center justify-around px-2 py-2">
            {navItems.slice(0, 5).map((item) => {
              const isActive = pathname === item.path;
              return (
                <Link
                  key={item.path}
                  href={item.path}
                  className={`flex flex-col items-center gap-1 px-3 py-1.5 rounded-xl transition-all ${
                    isActive ? 'text-light-primary' : 'text-light-muted dark:text-dark-muted'
                  }`}
                >
                  <motion.span
                    animate={isActive ? { scale: 1.2, y: -2 } : { scale: 1, y: 0 }}
                    className="text-lg"
                  >
                    {item.icon}
                  </motion.span>
                  <span className="text-[10px] font-medium">{item.label}</span>
                  {isActive && <div className="w-1 h-1 rounded-full bg-light-primary" />}
                </Link>
              );
            })}
          </div>
        </motion.nav>
      )}

      {/* Mobile Menu Overlay */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="md:hidden fixed inset-0 bg-black/50 z-40"
              onClick={() => setMobileMenuOpen(false)}
            />
            <motion.div
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              transition={{ type: 'spring', damping: 30 }}
              className="md:hidden fixed left-0 top-0 bottom-0 w-72 glass-strong z-50 flex flex-col p-4"
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl overflow-hidden relative">
                    <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
                  </div>
                  <div>
                    <h1 className="gradient-text font-bold text-sm">{APP_NAME}</h1>
                    <p className="text-xs text-light-muted dark:text-dark-muted">Timi</p>
                  </div>
                </div>
                <button onClick={() => setMobileMenuOpen(false)} className="text-light-muted text-2xl" aria-label="Close mobile menu">✕</button>
              </div>

              <nav className="flex-1 space-y-1">
                {navItems.map((item) => {
                  const isActive = pathname === item.path;
                  return (
                    <Link
                      key={item.path}
                      href={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                        isActive
                          ? 'text-white font-medium'
                          : 'text-light-muted dark:text-dark-muted'
                      }`}
                      style={isActive ? { background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)' } : {}}
                    >
                      <span className="text-xl">{item.icon}</span>
                      <span className="text-sm">{item.label}</span>
                    </Link>
                  );
                })}
              </nav>

              <div className="border-t border-light-border/50 dark:border-dark-border/50 pt-4 space-y-3">
                <div className="flex items-center gap-3 px-4">
                  {user.photoURL && <img src={user.photoURL} alt="" className="w-8 h-8 rounded-full ring-2 ring-light-primary/30" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-light-text dark:text-dark-text truncate">{user.displayName}</p>
                    <p className="text-xs text-light-muted dark:text-dark-muted truncate">{user.email}</p>
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2 rounded-xl text-light-muted dark:text-dark-muted hover:bg-light-primary/10 hover:text-light-primary transition-colors text-sm"
                >
                  <span className="text-lg">🚪</span>
                  <span>Sign Out</span>
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main
        className={`flex-1 transition-all duration-300 ${isMobile ? 'pb-20' : ''}`}
        style={{ marginLeft: isMobile ? 0 : sidebarOpen ? 260 : 80 }}
      >
        {/* Desktop Top Bar */}
        {!isMobile && (
        <div className="hidden md:flex items-center justify-end p-3 glass-strong sticky top-0 z-30 gap-3">
          <span className="text-sm font-medium text-light-muted dark:text-dark-muted tabular-nums">{currentTime}</span>
          <NotificationCenter />
          <ThemeToggle />
        </div>
        )}

        {/* Mobile Header */}
        {isMobile && (
          <div className="md:hidden flex items-center justify-between p-4 glass-strong sticky top-0 z-30">
            <button onClick={() => setMobileMenuOpen(true)} className="text-light-text dark:text-dark-text text-2xl" aria-label="Open mobile menu">☰</button>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-light-muted dark:text-dark-muted tabular-nums">{currentTime}</span>
              <NotificationCenter />
              <ThemeToggle />
            </div>
            <div className="w-8 h-8 rounded-full overflow-hidden ring-2 ring-light-primary/30">
              {user.photoURL && <img src={user.photoURL} alt={user.displayName || 'User avatar'} className="w-full h-full object-cover" />}
            </div>
          </div>
        )}

        <div className="p-4 md:p-6 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
