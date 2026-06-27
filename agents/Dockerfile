FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# torch is large; keep as separate cached layer
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# uv resolves dependencies ~10-50x faster than pip
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

CMD ["python", "main.py"]
