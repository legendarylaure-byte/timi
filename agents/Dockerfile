FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch is large; keep as separate cached layer
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# pip install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
