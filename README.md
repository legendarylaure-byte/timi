# Vyom Ai Cloud — Timi

> **AI-Powered Tech Educational Video Platform**
> Fully automated video creation and multi-platform publishing for AI/tech educational content.

## Overview

Vyom Ai Cloud (codename: Timi) is an automated content pipeline that generates educational tech/AI videos — from script to publish — across YouTube, TikTok, Instagram, and Facebook. Eight CrewAI agents orchestrate the full workflow: scriptwriting, scene routing (Blender 3D diagrams, PIL mockups, stock footage), voiceover (Edge TTS), background music (MusicGen), xfade compositing, and multi-platform upload with API-native AI disclosure.

### Content Categories
| Category | Description |
|----------|-------------|
| AI Explained | How AI and ML technologies work, explained simply |
| Deep Tech | In-depth technical deep dives and architecture breakdowns |
| Paper Breakdowns | Latest research papers summarized and analyzed |
| Tool Tutorials | Hands-on tutorials for AI tools and frameworks |
| Industry Analysis | Tech industry trends, predictions, and news analysis |
| Code & Build | Learn to build with code — projects and examples |
| AI News | Weekly AI and technology news roundup |
| Career & Learning | Tech career advice, learning paths, and resources |

### Output Formats
| Format | Aspect Ratio | Duration | Platforms |
|--------|-------------|----------|-----------|
| Shorts | 9:16 | Up to 120s | YouTube Shorts, TikTok, Instagram Reels |
| Long | 16:9 | Up to 300s | YouTube, Facebook |

### Daily Quota
- 2 Shorts videos
- 2 Long videos

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   Dashboard (Next.js)│────▶│  AI Agents (CrewAI)  │────▶│  Pipeline (FFmpeg)│
│   timi.vyomai.cloud  │     │  Groq/Gemini LLM     │     │  + xfade compose  │
└─────────────────────┘     └──────────────────────┘     └─────────────────┘
         │                          │                            │
    Firebase              Cloudflare R2 (temp)          YouTube/TikTok/
  (Auth/DB)            (videos auto-deleted)             Instagram/FB
         │                          │                            │
                    Telegram Bot ──────────────► Notifications
```

### Scene Asset Routing
```
┌──────────────┐
│  Scene Parser │──▶ STOCK_FOOTAGE ──▶ Pexels API
│  (keywords)   │──▶ DIAGRAM_3D ──▶ Blender (Python templates)
└──────────────┘──▶ SCREEN_CAPTURE ──▶ PIL mockups
                   └──▶ CODE_SNIPPET ──▶ PIL mockup
```

## Tech Stack

### Frontend
- Next.js 15 + React 19 + TypeScript
- Framer Motion + TailwindCSS
- Firebase Auth (Google OAuth)
- lucide-react (SVG icons)
- Dark/light theme

### AI Agents
- CrewAI + LangChain (multi-agent orchestration)
- Groq API + Gemini API (LLM inference)
- Edge TTS (voice synthesis)
- MusicGen (background music)

### Video Pipeline
- Blender 4.x LTS (3D Branch Education-style photorealistic renders)
- FFmpeg 8.1 (xfade compositing with dissolve/fade/slide transitions)
- PIL/Pillow (terminal/IDE/browser/code mockups)
- Pexels API (stock footage)

### Infrastructure
- Vercel (frontend hosting — free)
- Firebase (auth, database — free tier)
- Cloudflare R2 (video storage — 10GB free, auto-delete)
- python-telegram-bot (notifications)
- APScheduler (task scheduling)

### Compliance
- YouTube `containsSyntheticMedia` (API-native AI disclosure)
- TikTok `is_aigc` (Content Posting API)
- Instagram `is_ai_generated` (Graph API)
- Facebook fallback `#AI` hashtag

## Project Structure

```
timi/
├── dashboard/              # Next.js frontend application
├── agents/                 # Python AI agent scripts
│   ├── crew/               # CrewAI agent definitions
│   ├── utils/              # Shared utilities (video, audio, thumbnails)
│   ├── compliance/         # AI disclosure & platform policy
│   └── data/               # Affiliate programs, prompts
├── firebase/               # Firebase configuration
├── .github/workflows/      # CI/CD pipelines
├── vercel.json             # Vercel deployment config
└── README.md               # This file
```

## Setup

### Prerequisites
- Node.js 20+
- Python 3.11+ (3.14.x)
- FFmpeg 8.0+ (with xfade filter support)
- Blender 4.x LTS (optional — for 3D diagram renders)
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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Test the Full Pipeline

```bash
cd agents
source .venv/bin/activate
python test_transformers.py
```

## Agent Roles

| Agent | Responsibility |
|-------|---------------|
| Scriptwriter | Researches and writes educational tech scripts |
| Storyboard Artist | Generates scene descriptions with asset type routing |
| Voice Actor | Synthesizes narration (Edge TTS) |
| Composer | Creates background music |
| Asset Generator | Routes scenes to Blender/PIL/Pexels |
| Video Editor | xfade composites assets with audio |
| Thumbnail Creator | Renders Pillow thumbnails with title text |
| Publisher | Uploads with compliance flags to all platforms |

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot |
| `/status` | Current pipeline status |
| `/today` | Videos generated/uploaded today |
| `/analytics` | Channel growth metrics |
| `/youtube` | YouTube channel stats |
| `/pause` | Pause the pipeline |
| `/resume` | Resume the pipeline |
| `/cleanup` | Delete old uploaded videos from storage |
| `/query <question>` | Ask about the project |

## Monetization Strategy

### Revenue Streams
1. YouTube Partner Program (1K subs + 4K watch hours / 10M Shorts views)
2. TikTok Creator Rewards Program (10K followers + 100K views)
3. Instagram Subscriptions (10K followers + 60K watch mins)
4. Facebook In-Stream Ads
5. AI tool affiliate marketing
6. Brand sponsorships

### CPM Ranges (Tech/AI Education)
| Platform | CPM |
|----------|-----|
| YouTube | $8.00 - $15.00 |
| TikTok | $1.00 - $4.00 |
| Instagram | $3.00 - $8.00 |
| Facebook | $2.00 - $6.00 |

## Cost Breakdown (Monthly)

| Service | Cost |
|---------|------|
| Vercel Hosting | $0 |
| Firebase (Free tier) | $0 |
| Groq API (Free tier) | $0 |
| Gemini API (Free tier) | $0 |
| Pexels API (Free tier) | $0 |
| Cloudflare R2 (10GB free) | $0 |
| Telegram Bot | $0 |
| **Total** | **~$0/month** |

## License

MIT — Open Source
