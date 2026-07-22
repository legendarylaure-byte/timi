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
    && rm -rf /var/lib/apt/lists/*

ARG BLENDER_VERSION=4.5.12
RUN curl -fsSL "https://download.blender.org/release/Blender4.5/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    | tar -xJ -C /opt && \
    ln -s /opt/blender-${BLENDER_VERSION}-linux-x64/blender /usr/local/bin/blender && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir torch --extra-index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -m playwright install chromium --with-deps

COPY . .

CMD ["python", "main.py"]
