"""Mutation harness: reintroduce each bug, confirm exactly one layer fails.

Run:  python3 agents/scripts/guard_mutations.py

Why: a test that cannot fail is worse than no test (D39), and an output-side
`-t` once masked a reverted `d` so four green tests proved nothing (D46). Each
mutation below is a single, surgical revert of the fix, run in its own
container so no two mutations can interact.

Binding the mutated HOST file over the image path keeps this fast (no rebuild)
while still testing the real container environment -- the same `--env-file` +
SA-key invocation verify.sh uses, because a bare `docker run` drops ~40 vars
and silently selects the wrong TTS provider (D37).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
SA = ROOT / "firebase" / "serviceAccountKey.json"

# (name, relative file, [(find, replace), ...], tests to run)
MUTATIONS = [
    (
        "M1 main.py naive timestamp (the original bug)",
        "main.py",
        [(
            """                    last_activity = datetime.fromtimestamp(
                        ts.timestamp(), tz=timezone.utc
                    )""",
            "                    last_activity = datetime.utcfromtimestamp(ts.timestamp())",
        )],
        "tests/test_overnight_guards.py",
    ),
    (
        "M2 check_staleness naive normalisation removed",
        "utils/alert_manager.py",
        [(
            """    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)""",
            "    pass  # naive normalisation removed",
        )],
        "tests/test_overnight_guards.py",
    ),
    (
        "M3 pipeline_guard_job back to one shared try/except",
        "main.py",
        [(
            """    db = get_firestore_client()
    _run_guard("staleness", lambda: _guard_staleness(db))
    _run_guard("system_resources", lambda: _guard_system_resources(db))
    _run_guard("daily_volume", lambda: _guard_daily_volume(db))
    _run_guard("run_produced_today", lambda: _guard_run_produced_today(db))""",
            """    db = get_firestore_client()
    try:
        _guard_staleness(db)
        _guard_system_resources(db)
        _guard_daily_volume(db)
        _guard_run_produced_today(db)
    except Exception as e:
        log_event("ALERT", f"guards failed: {e}", "debug")""",
        )],
        "tests/test_overnight_guards.py",
    ),
    (
        "M4 alert cooldown removed",
        "utils/alert_manager.py",
        [(
            """        last = _alert_last_sent.get(alert_type)
        if last is not None and (time.time() - last) < ALERT_COOLDOWN_HOURS * 3600:""",
            """        last = None
        if False:""",
        )],
        "tests/test_overnight_guards.py",
    ),
    (
        "M5 guard job never registered with the scheduler",
        "main.py",
        [(
            'scheduler.add_job(pipeline_guard_job, "interval", minutes=15, misfire_grace_time=120)',
            "pass  # pipeline_guard_job removed from scheduler",
        )],
        "tests/test_overnight_guards.py",
    ),
    (
        "M6 no-firestore early return removed (read failure reported as no output)",
        "main.py",
        [(
            """    if not db:
        return

    now_utc = datetime.now(timezone.utc)""",
            """    now_utc = datetime.now(timezone.utc)""",
        )],
        "tests/test_overnight_guards.py",
    ),
    (
        "M7 daily_volume target back to SCHEDULE_* sum (3 instead of 5)",
        "main.py",
        [(
            "    slate = daily_slate()",
            """    slate = {
        "shorts": int(os.environ.get("SCHEDULE_SHORTS_PER_DAY", "1")),
        "longs": int(os.environ.get("SCHEDULE_LONG_PER_DAY", "2")),
        "total": int(os.environ.get("SCHEDULE_SHORTS_PER_DAY", "1"))
        + int(os.environ.get("SCHEDULE_LONG_PER_DAY", "2")),
    }""",
        )],
        "tests/test_overnight_guards.py tests/test_daily_volume.py",
    ),
    (
        "M8 short path back to 'upload_failed' for a 0/0 render (the original bug)",
        "main.py",
        [(
            """        short_status = "render_only" if _render_only() else (
            "scheduled" if publish_at else ("uploaded" if (youtube_url or publish_result.get("success_count", 0) > 0) else "upload_failed")
        )""",
            """        short_status = "scheduled" if publish_at else ("uploaded" if (youtube_url or publish_result.get("success_count", 0) > 0) else "upload_failed")""",
        )],
        "tests/test_render_only_status.py",
    ),
    (
        "M9 long path back to 'upload_failed' for a 0/0 render",
        "main.py",
        [(
            """        final_status = "render_only" if _render_only() else (
            "uploaded" if (youtube_url or publish_result.get("success_count", 0) > 0) else "upload_failed"
        )""",
            """        final_status = "uploaded" if (youtube_url or publish_result.get("success_count", 0) > 0) else "upload_failed\"""",
        )],
        "tests/test_render_only_status.py",
    ),
    (
        "M10 long path hardcodes upload_failed into add_video_record",
        "main.py",
        [(
            'add_video_record(video_id, topic, "long", final_status, category=category)',
            'add_video_record(video_id, topic, "long", "upload_failed", category=category)',
        )],
        "tests/test_render_only_status.py",
    ),
    (
        "M11 render_only boolean dropped from one persist site",
        "main.py",
        [(
            """            "status": final_status,
            "render_only": _render_only(),""",
            """            "status": final_status,""",
        )],
        "tests/test_render_only_status.py",
    ),
    (
        "M12 render_only inferred from an empty platform list instead of the switch",
        "main.py",
        [(
            """def _render_only() -> bool:""",
            """def _render_only() -> bool:
    return not _platforms_to_publish() or (""",
        )],
        "tests/test_render_only_status.py",
    ),
]


def run_tests(overlay_file, tests):
    """Run pytest in the real container with `overlay_file` bind-mounted over the image copy."""
    target = "/app/" + str(overlay_file.relative_to(AGENTS))
    cmd = [
        "docker", "run", "--rm", "-i",
        "--env-file", str(AGENTS / ".env"),
        "-v", f"{SA}:/app/firebase/serviceAccountKey.json:ro",
        "-v", f"{AGENTS}/tests:/app/tests:ro",
        "-v", f"{AGENTS}/data/brand:/app/data/brand:ro",
        "-v", f"{overlay_file}:{target}:ro",
        "timi-pipeline:guardtest",
        "python3", "-m", "pytest", *tests.split(), "-q", "--no-header", "-p", "no:cacheprovider",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def failed_tests(output):
    names = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            names.append(line.split()[1].split("::")[-1])
    return names


def main():
    failures = []
    for name, rel, edits, tests in MUTATIONS:
        src = AGENTS / rel
        backup = src.read_text()
        mutated = backup
        try:
            for find, replace in edits:
                if find not in mutated:
                    print(f"  SKIP  {name}: anchor not found -- the code moved, fix the harness")
                    failures.append(name)
                    mutated = None
                    break
                mutated = mutated.replace(find, replace, 1)
            if mutated is None:
                continue

            src.write_text(mutated)
            result = run_tests(src, tests)
            caught = failed_tests(result.stdout + result.stderr)
            verdict = "CAUGHT " if caught else "MISSED "
            print(f"  {verdict} {name}")
            print(f"           failing: {', '.join(caught) or '(none -- THE MUTATION SURVIVED)'}")
            if not caught:
                failures.append(name)
        finally:
            src.write_text(backup)

    print()
    if failures:
        print(f"FAILED: {len(failures)} mutation(s) not caught by any test:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASSED: all {len(MUTATIONS)} mutations caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
