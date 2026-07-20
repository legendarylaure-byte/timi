FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    curl \
    procps \
    libcairo2-dev \
    libpango1.0-dev \
    pango1.0-tools \
    libglib2.0-dev \
    patchelf \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch is large; keep as separate cached layer
# Use --extra-index-url so pip can fall back to PyPI if the CPU index
# doesn't have a matching wheel for this platform/version.
RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

# pip install remaining dependencies (torch already installed above,
# so -r requirements.txt won't download it again)
RUN pip install --no-cache-dir -r requirements.txt

# install playwright browsers (for community posts automation)
RUN python3 -m playwright install chromium --with-deps

COPY . .

CMD ["python", "main.py"]
