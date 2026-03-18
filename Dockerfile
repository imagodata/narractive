# =============================================================================
# Video Automation — Headless Frame Capture
# =============================================================================
# Runs an application in a virtual framebuffer (Xvfb), captures frames via
# scrot/import, and assembles final video with FFmpeg. No OBS required.
#
# Build:
#   docker build -t video-automation .
#
# Run:
#   docker run --rm -v $(pwd)/output:/app/output video-automation --all --sequences-package my_plugin.sequences
#
# For application-specific images, extend this Dockerfile:
#   FROM video-automation:latest
#   RUN apt-get install -y my-application
# =============================================================================

FROM ubuntu:22.04

LABEL maintainer="Video Automation"
LABEL description="Headless frame capture + FFmpeg for desktop application video automation"

ENV DEBIAN_FRONTEND=noninteractive

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xdotool \
    wmctrl \
    openbox \
    scrot \
    imagemagick \
    ffmpeg \
    python3-pip \
    python3-dev \
    python3-tk \
    python3-xlib \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    dbus-x11 \
    at-spi2-core \
    procps \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ──────────────────────────────────────────────────────────
COPY requirements-docker.txt /tmp/requirements-docker.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements-docker.txt \
    && rm /tmp/requirements-docker.txt

# ── Playwright for diagram rendering (optional) ─────────────────────────────
RUN pip3 install --no-cache-dir --break-system-packages playwright \
    && python3 -m playwright install --with-deps chromium \
    || echo "Playwright install failed (optional)"

# ── Xvfb configuration ──────────────────────────────────────────────────────
ENV DISPLAY=:99
ENV RESOLUTION=1920x1080x24
ENV QT_QPA_PLATFORM=xcb

# ── Working directory ────────────────────────────────────────────────────────
WORKDIR /app
COPY . /app/

# ── Application mount point ──────────────────────────────────────────────────
# Mount application data or plugins at runtime:
#   -v /path/to/data:/data:ro
VOLUME ["/app/output"]

# ── Entrypoint ───────────────────────────────────────────────────────────────
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["--help"]
