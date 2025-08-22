#FROM ai-base:latest as stage1
FROM dustynv/nano_llm:r36.4.0 AS stage1

ENV CUDA_HOME=/usr/local/cuda

ENV BLINKA_FORCECHIP=T234
ENV BLINKA_FORCEBOARD=JETSON_ORIN_NANO
ENV JETSON_MODEL_NAME=JETSON_ORIN_NANO

WORKDIR /


COPY ./scripts/entrypoint.sh /
COPY ./scripts/felix.sh /
COPY ./scripts/train.sh /

RUN apt-get update && apt-get -y install vim i2c-tools libzmq3-dev libzmq5 pkg-config 

# apt install -y gstreamer1.0-nice
# apt-get install -y avahi-utils libnss-mdns 
# service avahi-daemon stop

RUN apt install -y gstreamer1.0-nice
RUN apt-get install -y avahi-utils libnss-mdns \
   && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip
RUN pip3 install --no-cache-dir --verbose --index-url https://pypi.org/simple \
  pyserial \
  flask \
  flask_cors \
  pandas \
  asyncio-atexit \
  adafruit-blinka \
  adafruit-circuitpython-vl53l0x \
  jetson.GPIO \
  click \
  nicegui \
  smbus2

FROM stage1 AS stage2

#ENTRYPOINT ["/entrypoint.sh"]

RUN echo "source /entrypoint.sh" >> /root/.bashrc

# DOCKER_BUILDKIT=1 docker build -f Dockerfile -t felix:latest .
# https://www.ros.org/reps/rep-2001.html#id25
