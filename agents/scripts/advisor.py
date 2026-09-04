"""
Local AI Improvement Advisor (strategy prompt generator).

Run standalone on this Mac (or in the timi container) to have the LOCAL Ollama
model read your latest pipeline performance and produce a copy-paste enhancement
prompt you can hand to any AI coding assistant.

No cloud AI is used — only the local Ollama model.

Examples:
  python -m agents.scripts.advisor                      # full self-contained run
  python -m agents.scripts.advisor --dry-run            # show data, skip LLM
  python -m agents.scripts.advisor --json               # machine readable output
"""
import argparse
import base64
import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

# Standalone: direct import of firebase_admin (no heavy agents.utils package,
# which eagerly imports the whole pipeline and breaks on `utils.*` abs imports).
import firebase_admin  # noqa: E402
from firebase_admin import credentials, firestore  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.dirname(HERE)
_ROOT = os.path.dirname(AGENTS_DIR)
load_dotenv(os.path.join(_ROOT, '.env'))
load_dotenv(os.path.join(AGENTS_DIR, '.env'))

_FIREBASE_APP = None


def _get_client():
    global _FIREBASE_APP
    key_b64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY', '')
    key_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH', '')
    if key_b64:
        try:
            sa = json.loads(base64.b64decode(key_b64).decode())
        except Exception as e:
            print(f"ERROR: failed to decode FIREBASE_SERVICE_ACCOUNT_KEY: {e}")
            return None
    elif key_path and os.path.exists(key_path):
        try:
            sa = json.loads(open(key_path).read())
        except Exception as e:
            print(f"ERROR: failed to load service account file {key_path}: {e}")
            return None
    else:
        print("ERROR: No FIREBASE_SERVICE_ACCOUNT_KEY in .env — cannot read data.")
        return None
    try:
        if _FIREBASE_APP is None:
            _FIREBASE_APP = firebase_admin.initialize_app(
                credentials.Certificate(sa),
                {'projectId': sa.get('project_id')},
            )
        return firestore.client(_FIREBASE_APP)
    except Exception as e:
        print(f"ERROR: Firestore init failed: {e}")
        return None


def _n(v):
    try:
        if isinstance(v, str):
            return float(v.replace(',', ''))
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _gather():
    db = _get_client()
    if db is None:
        return None

    channel = db.collection('system').document('channel_stats').get().to_dict() or {}
    revenue = db.collection('monetization').document('revenue').get().to_dict() or {}

    videos = []
    for d in db.collection('videos').order_by('created_at', direction=1).limit(30).get():
        data = d.to_dict()
        videos.append({
            'title': data.get('title', ''),
            'format': data.get('format', ''),
            'category': data.get('category', ''),
            'status': data.get('status', ''),
            'views': int(_n(data.get('views'))),
            'likes': int(_n(data.get('likes'))),
            'comments': int(_n(data.get('comments'))),
            'quality_score': float(_n(data.get('quality_score'))),
            'virality_score': float(_n(data.get('virality_score'))),
            'predicted_7d': int(_n(data.get('predicted_views_7d'))),
            'predicted_30d': int(_n(data.get('predicted_views_30d'))),
            'watch_hours': float(_n(data.get('estimated_watch_hours'))),
            'platforms': data.get('published_platforms', []),
        })

    metrics = {'total_runs': 0, 'successes': 0, 'failures': []}
    for d in db.collection('pipeline_metrics').order_by('created_at', direction=1).limit(60).get():
        data = d.to_dict()
        metrics['total_runs'] += 1
        if data.get('success'):
            metrics['successes'] += 1
        else:
            metrics['failures'].append({
                'topic': data.get('topic', ''),
                'format': data.get('format', ''),
            })

    agent_states = []
    for d in db.collection('agent_status').get():
        data = d.to_dict()
        agent_states.append({
            'id': data.get('agent_id'),
            'status': data.get('status'),
            'action': data.get('current_action', ''),
        })

    return {
        'channel': channel,
        'revenue': revenue,
        'videos': videos,
        'metrics': metrics,
        'agent_states': agent_states,
    }


def _build_context(data, notes):
    ch = data['channel']
    rev = data['revenue']
    runs = data['metrics']['total_runs']
    succ = data['metrics']['successes']
    rate = round((succ / runs) * 100) if runs else 0
    failures = data['metrics']['failures'][-8:]

    lines = [
        "You are helping improve an automated AI video pipeline (Timi) that builds and",
        "publishes shorts + long-form videos to YouTube, TikTok, Instagram, and Facebook.",
        "The goal is viral reach and monetization. Below is the real recent production data.",
        "",
    ]
    lines.append(f"CHANNEL: {ch.get('channel_name', 'Legendary Laure')}")
    lines.append(f"  - Subscribers: {int(_n(ch.get('subscribers')))}")
    lines.append(f"  - Total views: {int(_n(ch.get('total_views')))}")
    lines.append(f"  - Watch hours: {round(_n(ch.get('total_watch_hours')), 1)}")
    lines.append(f"REVENUE: current month ${rev.get('currentMonth', 0)}, est. yearly ${rev.get('estimatedYearly', 0)}")
    lines.append(f"PIPELINE: {succ}/{runs} runs succeeded ({rate}% success), last failures: {len(failures)}")
    for f in failures[-4:]:
        lines.append(f"    - failed: {f.get('topic', '?')} ({f.get('format', '?')})")

    if data['videos']:
        lines.append(f"RECENT {len(data['videos'])} VIDEOS:")
        for v in data['videos'][-12:]:
            lines.append(
                f"  - [{v['format']}] '{v['title']}' views={v['views']} likes={v['likes']} "
                f"q={v['quality_score']} vira={v['virality_score']} pred7d={v['predicted_7d']} "
                f"pred30d={v['predicted_30d']} platforms={','.join(v['platforms']) or 'none'}"
            )

    if notes:
        lines.append("")
        lines.append("USER PRIORITIES/NOTES (please weigh heavily):")
        lines.append(f"  {notes}")

    return "\n".join(lines)


def _prompt(context):
    return f"""{context}

============= YOUR TASK =============
Read the above production data and produce a CONCRETE, copy-paste-ready improvement
prompt for an AI coding assistant that upgrades this pipeline.

The prompt must be addressed to the assistant as "You are upgrading the Timi pipeline."

Structure the output as a 3-PART brief:
PART 1 — WHAT TO FIX (the 2-4 highest-leverage issues right now: e.g. a platform that
fails, a format that underperforms, a rendering bottleneck, low virality, low watch time,
monetization progress). Rank by impact on subscribers/views/revenue. Quote the real numbers.
PART 2 — WHERE (concrete file paths + the exact change). Use known pipeline paths such as
agents/main.py, agents/crew/scriptwriter.py, agents/utils/multi_platform_publisher.py,
agents/utils/video_compositor.py, agents/utils/shorts_renderer.py, agents/utils/voice_gen.py,
agents/utils/trend_discovery.py, agents/utils/music_gen.py. Point to the specific function.
PART 3 — ACCEPTANCE CHECK (how to verify the change worked, e.g. the metric that must move,
or a command to rerun).

Keep it actionable: an engineer should be able to start immediately. No fluff, no filler.
Do not invent data that is not in the context above."""


def _ask_ollama(prompt, model, base):
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.4},
    }
    r = httpx.post(f"{base}/api/generate", json=payload, timeout=180)
    r.raise_for_status()
    return r.json().get('response', '').strip()


def _pick_model(base):
    try:
        names = [m.get('name', '') for m in httpx.get(f"{base}/api/tags", timeout=8).json().get('models', [])]
    except Exception as e:
        print(f"WARN: could not list Ollama models: {e}")
        names = []
    for pref in (os.getenv('OLLAMA_MODEL', 'qwen2.5:7b'), 'gemma3:4b'):
        if any(pref in n for n in names):
            return pref
    return 'qwen2.5:7b'


def main():
    parser = argparse.ArgumentParser(description='Local AI pipeline-improvement advisor')
    parser.add_argument('--dry-run', action='store_true', help='Print context, skip LLM call')
    parser.add_argument('--json', action='store_true', help='Emit JSON output')
    parser.add_argument('--manual-analysis', default='', help='Your own priority note')
    args = parser.parse_args()

    data = _gather()
    if data is None:
        sys.exit(1)

    context = _build_context(data, args.manual_analysis)

    base = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    model = _pick_model(base)

    if args.dry_run:
        print(context)
        return

    print(f"[ADVISOR] Using local model '{model}' at {base} …")
    prompt = _prompt(context)
    started = time.time()
    try:
        answer = _ask_ollama(prompt, model, base)
    except Exception as e:
        print(f"ERROR: Ollama call failed: {e}")
        print("\n--- CONTEXT (paste this into your AI instead) ---\n")
        print(context)
        sys.exit(1)

    if args.json:
        out = {'model': model, 'elapsed_sec': round(time.time() - started, 1), 'prompt': answer}
        print(json.dumps(out, indent=2))
    else:
        print("\n" + "=" * 60)
        print("COPY-PASTE ENHANCEMENT PROMPT  (hand this to your AI coding assistant)")
        print("=" * 60 + "\n")
        print(answer.strip())
        print("\n" + "=" * 60)
        print("Done. Paste the text above into your local AI coding session to build the improvement.")
        print("=" * 60)


if __name__ == '__main__':
    main()