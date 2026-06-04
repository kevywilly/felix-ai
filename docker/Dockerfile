FROM ultralytics/ultralytics:latest-jetson-jetpack6 AS stage1

# Jetson identity for Blinka
ENV BLINKA_FORCECHIP=T234
ENV BLINKA_FORCEBOARD=JETSON_ORIN_NANO
ENV JETSON_MODEL_NAME=JETSON_ORIN_NANO
ENV CLAUDE_CONFIG_DIR="/.claude"

# Pin pip away from the broken jetson.webredirect default
ENV PIP_INDEX_URL=https://pypi.org/simple

# System packages: GStreamer extras, I2C, mDNS, networking utils
RUN apt-get update && apt-get install -y --no-install-recommends \
      vim i2c-tools \
      libzmq3-dev libzmq5 pkg-config \
      gstreamer1.0-nice gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
      libsrtp2-dev libavdevice-dev libavfilter-dev \
      libopus-dev libvpx-dev \
      avahi-utils libnss-mdns \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Robotics: sensors, GPIO, serial, motor control
RUN pip3 install --no-cache-dir \
      pyserial \
      smbus2 \
      Jetson.GPIO \
      adafruit-blinka \
      adafruit-circuitpython-vl53l0x

# Web + teleop server
RUN pip3 install --no-cache-dir \
      flask flask-cors flask-sock \
      nicegui \
      click pandas asyncio-atexit

# WebRTC video path (aiortc + deps)
RUN pip3 install --no-cache-dir \
      aiortc \
      aiohttp \
      av

# The ultralytics jetpack base ships opencv-python-headless in
# /usr/local/lib, which shadows JetPack's GStreamer-enabled cv2 in
# /usr/lib. A headless wheel has GStreamer:NO, so cv2.VideoCapture(...,
# CAP_GSTREAMER) silently returns isOpened()==False and the CSI camera
# never opens. Remove the pip wheels so the system OpenCV (GStreamer:YES)
# is used, then assert GStreamer support at build time so a future base
# bump can't reintroduce the regression silently.
RUN pip3 uninstall -y opencv-python opencv-python-headless 2>/dev/null || true \
 && python3 -c "import cv2, sys; \
print('cv2:', cv2.__file__); \
sys.exit(0 if any(l.strip().startswith('GStreamer') and 'YES' in l for l in cv2.getBuildInformation().splitlines()) else 'cv2 lacks GStreamer support')"

# App scripts
COPY ./scripts/entrypoint.sh /
COPY ./scripts/felix.sh /
COPY ./scripts/train.sh /

# Node + Claude Code for in-container dev
FROM stage1 AS stage2
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code
RUN echo "source /entrypoint.sh" >> /root/.bashrc