export default function InstagramIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="0.5" y="0.5" width="23" height="23" rx="5.5" fill="url(#ig-grad)" />
      <defs>
        <linearGradient id="ig-grad" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F58529" />
          <stop offset="0.25" stopColor="#DD2A7B" />
          <stop offset="0.5" stopColor="#8134AF" />
          <stop offset="0.75" stopColor="#515BD4" />
          <stop offset="1" stopColor="#00AFF5" />
        </linearGradient>
      </defs>
      <rect x="5" y="5" width="14" height="14" rx="3.5" stroke="#fff" strokeWidth="1.3" fill="none" />
      <circle cx="12" cy="12" r="3.5" stroke="#fff" strokeWidth="1.3" fill="none" />
      <circle cx="16.5" cy="7.5" r="1" fill="#fff" />
    </svg>
  );
}
