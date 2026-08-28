import os
import sys
import urllib.request

main_ok = "main.py" in open("/proc/1/cmdline").read()

ollama_ok = False
try:
    base = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    ollama_ok = (
        urllib.request.urlopen(base + "/api/version", timeout=3).status == 200
    )
except Exception:
    ollama_ok = False

sys.exit(0 if (main_ok and ollama_ok) else 1)
