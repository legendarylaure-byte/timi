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
    libegl1-mesa-dev \
    libgl1-mesa-dri \
    mesa-utils \
    wget \
    xz-utils \
    fonts-freefont-ttf \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -m playwright install chromium --with-deps

COPY . .

RUN chmod +x /app/docker-start.sh

CMD ["/app/docker-start.sh"]
