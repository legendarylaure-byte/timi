"""Concurrent pipeline — Thread pool for parallel short+long generation."""
import os
import sys
import uuid
import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any
from threading import Semaphore

logger = logging.getLogger(__name__)

GPU_SEMAPHORE = Semaphore(1)

PIPELINE_TIMEOUT_MINUTES = int(os.getenv("PIPELINE_TIMEOUT_MINUTES", "180"))

_MLX_EVAL_EVERY = os.getenv("LTX2_DIT_EVAL_EVERY", "8")
os.environ.setdefault("LTX2_DIT_EVAL_EVERY", _MLX_EVAL_EVERY)


def _run_in_worker(func: Callable, args: tuple, kwargs: dict) -> dict:
    """Run a pipeline function in a worker thread with GPU semaphore."""
    result = {"success": False, "error": None, "video_id": None, "topic": None}
    pipeline_runtime_id = kwargs.pop("_pipeline_runtime_id", None)
    gpu_needed = kwargs.pop("_gpu", True)
    try:
        if pipeline_runtime_id:
            os.environ["PIPELINE_RUNTIME_ID"] = pipeline_runtime_id
        if gpu_needed:
            acquired = GPU_SEMAPHORE.acquire(timeout=600)
            if not acquired:
                result["error"] = "GPU semaphore timeout (10m wait exhausted)"
                return result
        try:
            func(*args, **kwargs)
            result["success"] = True
        finally:
            if gpu_needed:
                GPU_SEMAPHORE.release()
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        logger.error("[concurrent] Worker failed: %s\n%s", e, traceback.format_exc())
    return result


def run_concurrent_pipelines(jobs: list[dict]) -> list[dict]:
    """Run multiple pipeline jobs concurrently.

    Each job dict::
        {
            "func": generate_short_video,
            "args": (topic, category, video_id, publish_at),
            "kwargs": {},
            "name": "short-1",
            "gpu": True,
        }
    Returns list of result dicts in same order as jobs.
    """
    max_workers = min(len(jobs), int(os.getenv("CONCURRENT_PIPELINE_WORKERS", "2")))
    logger.info("[concurrent] Running %d pipeline(s) with %d worker(s)", len(jobs), max_workers)

    pipeline_runtime_id = str(uuid.uuid4())[:8]
    logger.info("[concurrent] Pipeline runtime ID: %s", pipeline_runtime_id)

    results = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut_map = {}
        for i, job in enumerate(jobs):
            func = job["func"]
            args = job.get("args", ())
            kwargs = job.get("kwargs", {})
            kwargs["_gpu"] = job.get("gpu", True)
            kwargs.setdefault("_pipeline_runtime_id", pipeline_runtime_id)
            fut = executor.submit(_run_in_worker, func, args, kwargs)
            fut_map[fut] = i

        for fut in as_completed(fut_map):
            idx = fut_map[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                results[idx] = {"success": False, "error": f"Unhandled: {e}"}

    for i, (job, res) in enumerate(zip(jobs, results)):
        status = "OK" if res["success"] else "FAIL"
        logger.info("[concurrent] %s: %s — %s", job.get("name", f"job-{i}"), status, res.get("error", ""))

    return results


def run_with_gpu_lock(func: Callable, *args, timeout: int = 600, **kwargs) -> Any:
    """Run a function with the GPU semaphore acquired."""
    acquired = GPU_SEMAPHORE.acquire(timeout=timeout)
    if not acquired:
        raise TimeoutError("GPU semaphore could not be acquired within timeout")
    try:
        return func(*args, **kwargs)
    finally:
        GPU_SEMAPHORE.release()
