# Vyom Ai Cloud — Timi

> **Faceless Kids Content Automation Platform**
> AI-powered 3D animated cartoon video generation and publishing for YouTube, TikTok, Instagram, and Facebook.

## Overview

Vyom Ai Cloud (codename: Timi) is a fully automated content creation pipeline that generates educational 3D animated cartoon videos for children aged 1-9. The system runs 24/7, producing and publishing content across multiple social media platforms daily.

### Content Types
- Bedtime stories
- Mythology stories (gods and goddesses)
- Self-learning (ABCs, numbers, colors, morals)
- Animated fables
- Science for kids

### Output Formats
| Format | Aspect Ratio | Duration | Platforms |
|--------|-------------|----------|-----------|
| Shorts | 9:16 | Up to 120s | TikTok, Instagram Reels, YouTube Shorts |
| Long | 16:9 | Up to 300s | YouTube, Facebook |

### Daily Quota
- 2 Shorts videos
- 2 Long videos

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   Dashboard (Next.js)│────▶│  AI Agents (CrewAI)  │────▶│  Pipeline (FFmpeg)│
│   timi.vyomai.cloud  │     │  Groq LLM            │     │  + Serverless GPU │
└─────────────────────┘     └──────────────────────┘     └─────────────────┘
         │                          │                            │
    Firebase              Cloudflare R2 (temp)          YouTube/TikTok/
  (Auth/DB)            (videos auto-deleted)             Instagram/FB
         │                          │                            │
                    Telegram Bot ──────────────► Notifications
```

## Tech Stack

### Frontend
- Next.js 15 + React 19 + TypeScript
- Three.js + React Three Fiber (3D animations)
- TailwindCSS + Framer Motion
- Firebase Auth (Google OAuth)

### AI Agents
- CrewAI + LangChain (multi-agent orchestration)
- Groq API (LLM inference — free tier)
- Piper TTS + Bark (voice synthesis)
- MusicGen (background music)
- Stable Video Diffusion (video frames)
- Stable Diffusion XL (images/thumbnails)

### Pipeline
- FFmpeg (video composition)
- Manim (mathematical animations)
- APScheduler (task scheduling)

### Infrastructure
- Vercel (frontend hosting — free)
- Firebase (auth, database — free tier)
- Cloudflare R2 (video storage — 10GB free, auto-delete)
- Modal/Replicate (serverless GPU — pay-per-use)
- GitHub Actions (CI/CD)
- python-telegram-bot (notifications)

## Project Structure

```
timi/
├── dashboard/              # Next.js frontend application
├── agents/                 # Python AI agent scripts
├── pipeline/               # FFmpeg rendering pipeline
├── bot/                    # Telegram notification bot
├── firebase/               # Firebase configuration
├── .github/workflows/      # CI/CD pipelines
├── vercel.json             # Vercel deployment config
└── README.md               # This file
```

## Setup

### Prerequisites
- Node.js 20+
- Python 3.11+
- FFmpeg installed
- Firebase project created

### Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

See `.env.example` for all required keys.

### Dashboard Setup

```bash
cd dashboard
npm install
npm run dev
```

### Agents Setup

```bash
cd agents
pip install -r requirements.txt
python main.py
```

### Bot Setup

```bash
cd bot
pip install -r requirements.txt
python bot.py
```

## Deployment

### Vercel (Dashboard)
```bash
cd dashboard
vercel --prod
```

### Firebase (Database + Storage)
```bash
firebase deploy --only firestore,storage
```

### Domain Configuration
Add CNAME record in Hostinger:
- Host: `timi`
- Type: `CNAME`
- Value: `cname.vercel-dns.com`

## Agent Roles

| Agent | Responsibility |
|-------|---------------|
| Scriptwriter | Creates age-appropriate scripts |
| Storyboard Artist | Generates scene descriptions and images |
| Voice Actor | Synthesizes character voices |
| Composer | Creates background music |
| Animator | Generates 3D animated frames |
| Editor | Composites video and audio |
| Thumbnail Creator | Generates eye-catching thumbnails |
| Metadata Writer | Writes SEO-optimized titles, descriptions, tags |
| Publisher | Uploads to all social media platforms |

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot |
| `/status` | Current project status |
| `/today` | Videos generated/uploaded today |
| `/analytics` | Channel growth metrics |
| `/youtube` | YouTube channel stats |
| `/pause` | Pause the pipeline |
| `/resume` | Resume the pipeline |
| `/cleanup` | Delete old uploaded videos from storage |
| `/query <question>` | Ask about the project |

## Monetization Strategy

### Revenue Streams
1. YouTube Partner Program (1K subs + 4K watch hours)
2. TikTok Creator Rewards Program (10K followers + 100K views)
3. Instagram Subscriptions
4. Facebook In-Stream Ads
5. Brand sponsorships
6. Merchandise

### Growth Targets
- Month 1-2: Build content library (60 videos/month)
- Month 3-4: Reach 1K YouTube subscribers
- Month 5-6: Enable monetization
- Month 7+: Scale to 10K+ subscribers

## Cost Breakdown (Monthly)

| Service | Cost |
|---------|------|
| Vercel Hosting | $0 |
| Firebase (Free tier) | $0 |
| Groq API (Free tier) | $0 |
| Serverless GPU (rendering) | ~$0.50-1.00 |
| Telegram Bot | $0 |
| **Total** | **~$1/month** |

## License

MIT — Open Source

## Contributing

This is a personal automation project. Contributions welcome.
