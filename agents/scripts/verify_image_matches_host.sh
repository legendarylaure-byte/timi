#!/usr/bin/env bash
# Assert the image contains exactly the host's runtime source.
#
# WHY THIS IS A SCRIPT AND NOT A ONE-LINER: on 09-28 this check was hand-rolled
# and reported all 8 changed files as MISMATCH on a perfectly good image --
# macOS `shasum` defaults to SHA-1 while Linux `sha256sum` is SHA-256, so it
# compared two different digests and never could have matched. The failure mode
# is not "it broke", it is "it cried wolf and I nearly trusted it", which is
# worse. One algorithm, both sides, no opportunity to mix them up.
#
# Usage:
#   agents/scripts/verify_image_matches_host.sh [file ...]
# With no args, checks every .py the Dockerfile.overlay COPYs. The image is
# always the RUNNING container's -- that is the thing a deploy actually
# produced. Override with CONTAINER=<name>.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONTAINER="${CONTAINER:-timi-pipeline}"

# Named on every run, in the summary and in any failure. Without this, checking
# the wrong container silently reports success: the default target is whatever
# is *running*, so a check aimed at a freshly built image but pointed at
# production says "matches" and verifies nothing.
IMAGE_DIGEST="$(docker inspect "$CONTAINER" --format '{{.Image}}' 2>/dev/null || echo '?')"
echo "parity target: container=${CONTAINER} image=${IMAGE_DIGEST}"

# `docker exec` needs a RUNNING container, and under `set -e` + `pipefail` the
# first failed exec aborts the whole script mid-loop -- it exits 1 having printed
# nothing, which is indistinguishable from a real mismatch. Fail loudly instead.
if [ "$(docker inspect "$CONTAINER" --format '{{.State.Running}}' 2>/dev/null || echo false)" != "true" ]; then
  echo "CONTAINER NOT RUNNING: '$CONTAINER' -- this script reads files via docker exec, so a created-but-not-started container can never be checked. Start it, or pass CONTAINER=<running name>." >&2
  exit 1
fi

if [ "$#" -gt 0 ]; then
  FILES=("$@")
else
  # The COPY list in agents/Dockerfile.overlay. Kept explicit on purpose: a
  # walk would also cover files the image deliberately does not ship.
  FILES=(main.py)
  while IFS= read -r f; do FILES+=("$f"); done < <(
    cd "$ROOT/agents" && find utils crew models scripts -name '*.py' -not -path '*__pycache__*' | sort
  )
fi

# One digest function, applied to both sides. `shasum -a 256` is used on the
# host rather than `sha256sum` because macOS ships the former; inside the
# container we call `shasum -a 256` too when available so the two agree by
# construction.
digest() { shasum -a 256 | awk '{print $1}'; }

fail=0
for f in "${FILES[@]}"; do
  host="$ROOT/agents/$f"
  [ -f "$host" ] || { echo "MISSING ON HOST: $f"; fail=1; continue; }
  h="$(digest < "$host")"
  # `|| true` is load-bearing. A file absent from the image makes `docker exec`
  # exit non-zero; with `pipefail` + `set -e` that aborted the script at the
  # FIRST missing file, so the one condition this script exists to report
  # ("NOT IN CONTAINER") was the one thing it could never report -- it just
  # exited 1 with no output. Swallow the status and let the empty $i test speak.
  i="$(docker exec "$CONTAINER" sh -c "sha256sum '/app/$f' 2>/dev/null || shasum -a 256 '/app/$f'" 2>/dev/null | awk '{print $1}' || true)"
  if [ -z "$i" ]; then
    printf '  %-46s NOT IN CONTAINER\n' "$f"
    fail=1
  elif [ "$h" != "$i" ]; then
    printf '  %-46s MISMATCH\n    host %s\n    img  %s\n' "$f" "$h" "$i"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "IMAGE DOES NOT MATCH HOST - do not trust this deploy." >&2
  exit 1
fi
printf "image matches host: %d file(s), sha256 on both sides (container=%s)\n" "${#FILES[@]}" "$CONTAINER"
