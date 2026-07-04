export default function FacebookIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="0.5" y="0.5" width="23" height="23" rx="5.5" fill="#1877F2" />
      <path d="M14.5 4.5h-2.3a3.3 3.3 0 00-3.3 3.3v1.5H7.2v2.5h1.7v7.5h2.8v-7.5h2l.5-2.5h-2.5V8a.8.8 0 01.8-.8h1.7V4.5h-1.7z" fill="#fff" />
    </svg>
  );
}
