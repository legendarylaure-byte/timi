import os
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)

GPU_WIRED_LIMIT = 14000


def prepare_gpu_for_generation():
    try:
        result = subprocess.run(
            ["sudo", "sysctl", "-w", f"iogpu.wired_lwm_mb={GPU_WIRED_LIMIT}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("[GPU] Wired limit raised to %d MB", GPU_WIRED_LIMIT)
            return True
        else:
            logger.warning("[GPU] Could not raise wired limit (sudoers configured?): %s",
                           result.stderr.strip())
            return False
    except FileNotFoundError:
        logger.warning("[GPU] sysctl not available")
        return False
    except Exception as e:
        logger.warning("[GPU] Unexpected error: %s", e)
        return False


def check_memory_pressure() -> dict:
    try:
        result = subprocess.run(
            ["memory_pressure"], capture_output=True, text=True, timeout=5,
        )
        if "System is memory pressure-relieved" in result.stdout:
            return {"pressure": "ok", "available_gb": -1}
        elif "memory-pressure" in result.stdout:
            return {"pressure": "warning", "available_gb": -1}
        else:
            return {"pressure": "unknown", "available_gb": -1}
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5,
        )
        stats = {}
        for line in result.stdout.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                val = val.strip().rstrip(".")
                if val.isdigit():
                    stats[key.strip()] = int(val)

        page_size = 16384
        free_pages = stats.get("Pages free", 0)
        inactive_pages = stats.get("Pages inactive", 0)
        available_bytes = (free_pages + inactive_pages) * page_size
        available_gb = available_bytes / (1024**3)

        if available_gb < 2.0:
            return {"pressure": "critical", "available_gb": round(available_gb, 1)}
        elif available_gb < 4.0:
            return {"pressure": "warning", "available_gb": round(available_gb, 1)}
        else:
            return {"pressure": "ok", "available_gb": round(available_gb, 1)}
    except Exception:
        return {"pressure": "unknown", "available_gb": -1}
