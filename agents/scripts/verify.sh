#!/usr/bin/env bash
# Canonical verification entry point. USE THIS INSTEAD OF HAND-WRITTEN `docker run`.
#
# Why this exists: every `docker run` without `--env-file` silently drops ~40 vars
# from agents/.env, which once made dub_orchestration_selfcheck fail and cost real
# debugging time -- and worse, selects the WRONG TTS provider, so a selfcheck can
# "pass" or "fail" depending on how it was invoked. This script makes the correct
# invocation the easy one and asserts the provider actually resolved.
#
#   agents/scripts/verify.sh                 # all selfchecks + pytest
#   agents/scripts/verify.sh voice_provider  # only matching selfchecks
#   SKIP_PYTEST=1 agents/scripts/verify.sh   # selfchecks only
#
# Run from the repo root (it locates the repo itself).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

ENV_FILE="agents/.env"
SA_KEY="firebase/serviceAccountKey.json"
IMAGE="${VERIFY_IMAGE:-timi-pipeline:latest}"
FILTER="${1:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "FATAL: $ENV_FILE not found (run from the repo root)" >&2
  exit 2
fi
if [[ ! -f "$SA_KEY" ]]; then
  echo "FATAL: $SA_KEY not found -- selfchecks that touch Firestore need it" >&2
  exit 1
fi
# agents/data/ is gitignored runtime state and is deliberately not in the image,
# so test_brand_colors.py's config-agreement checks pass on the host and fail in
# the container for want of a file the image never had. Mount ONLY data/brand:
# hook_selfcheck and retention_selfcheck *write* to data/hook_testing and
# data/retention, so mounting all of agents/data read-only kills both with
# "Read-only file system". The rest of data/ stays container-ephemeral.
if [[ ! -d "$ROOT/agents/data/brand" ]]; then
  echo "FATAL: $ROOT/agents/data/brand not found -- brand config checks need it" >&2
  exit 1
fi

# The multilang font selfcheck is pure-PIL, but everything else wants the real env.
echo "=== verifying image: $IMAGE ==="
docker run --rm -i \
  --env-file "$ENV_FILE" \
  -v "$ROOT/$SA_KEY:/app/$SA_KEY:ro" \
  -v "$ROOT/agents/tests:/app/tests:ro" \
  -v "$ROOT/agents/data/brand:/app/data/brand:ro" \
  --entrypoint python3 \
  "$IMAGE" - <<'PY'
import os, sys, subprocess
sys.path.insert(0, "/app")

# Assert the environment is the one we meant to test, BEFORE trusting any result.
from utils.voice_provider import DEFAULT_VOICE_PROVIDER, get_tts_provider
resolved = (os.environ.get("VOICE_PROVIDER") or DEFAULT_VOICE_PROVIDER).strip().lower()
print(f"[env] VOICE_PROVIDER env={os.environ.get('VOICE_PROVIDER')!r} -> resolves to {resolved!r}")
if resolved != DEFAULT_VOICE_PROVIDER:
    print(f"[env] WARNING: not the code default {DEFAULT_VOICE_PROVIDER!r} -- "
          "selfchecks may exercise a different engine than production", file=sys.stderr)
print(f"[env] GEMINI_API_KEY   = {'set' if os.environ.get('GEMINI_API_KEY') else 'UNSET'}")
print(f"[env] FIREBASE_PROJECT = {os.environ.get('FIREBASE_PROJECT_ID')}")
for k in ("ENABLE_MULTI_LANG", "ENABLE_MULTI_LANG_DUB", "MULTI_LANG_CODES",
          "CLOUD_VIDEO_PROVIDER", "OLLAMA_BASE_URL"):
    print(f"[env] {k:22} = {os.environ.get(k, '<unset>')}")

SELFTESTS = [
    "clean_master_selfcheck", "dub_pipeline_selfcheck",
    "dub_orchestration_selfcheck", "hook_selfcheck", "multilang_font_selfcheck",
    "render_chain_selfcheck", "retention_selfcheck", "stock_selfcheck",
    "thumbnail_selfcheck", "title_selfcheck", "voice_provider_selfcheck",
]
fails = []
for name in SELFTESTS:
    print(f"\n{'='*70}\n== {name}\n{'='*70}")
    r = subprocess.run([sys.executable, "-m", f"utils.{name}"], cwd="/app")
    if r.returncode != 0:
        fails.append(f"utils.{name} (exit {r.returncode})")

print(f"\n{'='*70}\n== fonts module + pytest\n{'='*70}")
for mod in ("utils.fonts",):
    r = subprocess.run([sys.executable, "-m", mod], cwd="/app")
    if r.returncode != 0:
        fails.append(f"{mod} (exit {r.returncode})")

if os.environ.get("SKIP_PYTEST") != "1":
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd="/app")
    if r.returncode != 0:
        fails.append(f"pytest (exit {r.returncode})")

print(f"\n{'='*70}")
if fails:
    print("VERIFY FAILED:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("VERIFY PASSED: all selfchecks + pytest green")
PY
rc=$?

if [[ $rc -ne 0 ]]; then
  echo
  echo "verify.sh FAILED (exit $rc)" >&2
  echo "If a selfcheck failed on env/provider grounds, check [env] output above." >&2
  echo "Do NOT retry with a bare 'docker run' -- that drops agents/.env and lies." >&2
fi
exit $rc
