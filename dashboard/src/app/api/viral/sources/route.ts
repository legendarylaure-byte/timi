import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';

// Verified news sources — mirrors the back-end VERIFIED_HOSTS in news_scraper.py
// so the dashboard shows the same allowlist the scraper uses.
const SOURCES = [
  { name: 'BBC World', category: 'World News (24hr)', lang: 'en', url: 'https://feeds.bbci.co.uk/news/world/rss.xml' },
  { name: 'The Guardian World', category: 'World News (24hr)', lang: 'en', url: 'https://www.theguardian.com/world/rss' },
  { name: 'Al Jazeera', category: 'World News (24hr)', lang: 'en', url: 'https://www.aljazeera.com/rss' },
  { name: 'Reuters World', category: 'World News (24hr)', lang: 'en', url: 'https://www.reuters.com/world/rss' },
  { name: 'Xinhua English', category: 'World News (24hr)', lang: 'en', url: 'http://www.news.cn/world/rss' },
  { name: 'NYT International', category: 'World News (24hr)', lang: 'en', url: 'https://www.nytimes.com/international/section/world.rss' },
  { name: 'The Kathmandu Post', category: 'Nepal News', lang: 'en', url: 'https://kathmandupost.com/rss' },
  { name: 'NepaliTimes', category: 'Nepal News', lang: 'en', url: 'https://nepalitimes.com/feed' },
  { name: 'OnlineKhabar EN', category: 'Nepal News', lang: 'en', url: 'https://english.onlinekhabar.com/feed/' },
  { name: 'Khabarhub', category: 'Nepal News', lang: 'en', url: 'https://english.khabarhub.com/feed' },
  { name: 'OnlineKhabar NP', category: 'Nepal News', lang: 'ne', url: 'https://www.onlinekhabar.com/feed' },
  { name: 'Office of PM Nepal', category: 'Nepal News', lang: 'en', url: 'https://opmcm.gov.np/rss' },
  { name: 'MoHA Nepal', category: 'Nepal News', lang: 'en', url: 'https://www.moha.gov.np/rss' },
];

export async function GET(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  return NextResponse.json({ sources: SOURCES });
}
