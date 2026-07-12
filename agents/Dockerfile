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
    texlive \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-science \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    dvipng \
    cm-super \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch is large; keep as separate cached layer
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# pip install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# install playwright browsers (for community posts automation)
RUN python3 -m playwright install chromium --with-deps

COPY . .

CMD ["python", "main.py"]
