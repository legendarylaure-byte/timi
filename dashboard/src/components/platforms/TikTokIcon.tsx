export default function TikTokIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="0.5" y="0.5" width="23" height="23" rx="5.5" fill="#000" />
      <path d="M16.5 4.5h-2.7v10.4a2.9 2.9 0 11-2.7-2.9v2.7a.2.2 0 00.2.2 0 0 0 0 2.5 2.5 0 100-5V4.5z" fill="#25F4EE" />
      <path d="M16.5 4.5h2.5v2.5a4.8 4.8 0 01-2.5-.1v5.5a4.3 4.3 0 11-4.2-4.3v2.7a1.7 1.7 0 101.7 1.6V4.5z" fill="#FE2C55" />
    </svg>
  );
}
