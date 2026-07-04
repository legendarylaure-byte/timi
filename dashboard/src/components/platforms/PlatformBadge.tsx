import YouTubeIcon from './YouTubeIcon';
import TikTokIcon from './TikTokIcon';
import InstagramIcon from './InstagramIcon';
import FacebookIcon from './FacebookIcon';

const platformConfig: Record<string, {
  label: string;
  color: string;
  Icon: (props: { size?: number }) => JSX.Element;
}> = {
  youtube: {
    label: 'YouTube',
    color: '#FF0000',
    Icon: YouTubeIcon,
  },
  tiktok: {
    label: 'TikTok',
    color: '#000000',
    Icon: TikTokIcon,
  },
  instagram: {
    label: 'Instagram',
    color: '#E4405F',
    Icon: InstagramIcon,
  },
  facebook: {
    label: 'Facebook',
    color: '#1877F2',
    Icon: FacebookIcon,
  },
};

interface PlatformBadgeProps {
  platform: string;
  url?: string;
  size?: 'sm' | 'md';
  showLabel?: boolean;
}

export default function PlatformBadge({ platform, url, size = 'sm', showLabel }: PlatformBadgeProps) {
  const key = platform.toLowerCase();
  const cfg = platformConfig[key];
  if (!cfg) return null;

  const iconSize = size === 'sm' ? 18 : 24;
  const content = (
    <span className="inline-flex items-center gap-1.5">
      <cfg.Icon size={iconSize} />
      {showLabel && (
        <span className="text-xs font-medium text-light-text dark:text-dark-text capitalize">
          {cfg.label}
        </span>
      )}
    </span>
  );

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
        title={`Open on ${cfg.label}`}
      >
        {content}
      </a>
    );
  }

  return content;
}

export { platformConfig };
