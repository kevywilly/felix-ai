# Felix Migration Brief: jetson-inference → ultralytics base + WebRTC teleop

## Context

Migrating Felix robot off the now-unmaintained `dustynv/jetson-inference` base image onto the actively-maintained `ultralytics/ultralytics:latest-jetson-jetpack6` base. Hardware is Jetson Orin Nano running JetPack 6, with VL53L0X TOF sensor, motor control via GPIO/I2C, and a camera (CSI or USB) for teleop and YOLO detection. The previous teleop attempt used MJPEG and felt laggy under driving, so video transport is being rebuilt on WebRTC (aiortc).

## What changed in the base image

**Already provided by the new base, do NOT reinstall:**
- ultralytics
- torch, torchvision (Jetson aarch64 + CUDA matched)
- onnxruntime-gpu
- TensorRT Python bindings
- onnx, onnxslim
- numpy, opencv (with GStreamer support, verify)

**Gone, must not be referenced anywhere in code:**
- `jetson_inference` Python module
- `jetson_utils` Python module (videoSource, videoOutput, cudaToNumpy, cudaImage)
- Anything importing from `jetson.inference` or `jetson.utils`

## What needs to be added on top

System packages:
- gstreamer1.0-nice, gstreamer1.0-plugins-bad, gstreamer1.0-plugins-ugly
- libsrtp2-dev, libavdevice-dev, libavfilter-dev
- libopus-dev, libvpx-dev
- i2c-tools, libzmq3-dev, libzmq5, pkg-config
- avahi-utils, libnss-mdns

Python packages (use `--index-url https://pypi.org/simple` because the base image's default index may be set to a Jetson-specific one):
- Robotics: pyserial, smbus2, Jetson.GPIO, adafruit-blinka, adafruit-circuitpython-vl53l0x
- Web/teleop: flask, flask-cors, flask-sock, nicegui, click, pandas, asyncio-atexit
- WebRTC: aiortc, aiohttp, av

## Code changes required

### 1. Video capture: replace jetson_utils with cv2 + GStreamer

Anywhere code currently does:
```python
from jetson_utils import videoSource, cudaToNumpy
cam = videoSource("csi://0")
img = cam.Capture()
frame = cudaToNumpy(img)
```

Replace with:
```python
import cv2
GST = ("nvarguscamerasrc sensor-id=0 ! "
       "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
       "nvvidconv ! video/x-raw, width=640, height=360, format=BGRx ! "
       "videoconvert ! video/x-raw, format=BGR ! "
       "appsink drop=1 max-buffers=1")
cap = cv2.VideoCapture(GST, cv2.CAP_GSTREAMER)
ok, frame = cap.read()
```

For USB webcam instead of CSI, swap `nvarguscamerasrc sensor-id=0` for `v4l2src device=/dev/video0`.

The `drop=1 max-buffers=1` on appsink is critical to prevent latency buildup. Use a background thread that continuously calls `cap.read()` and stores the latest frame, never let consumers pull frames in their own timing.

### 2. Video output: replace jetson_utils webrtc with aiortc

Anywhere code currently does:
```python
out = videoOutput("webrtc://@:8554/out")
out.Render(img)
```

Replace with an aiortc-based WebRTC server. Architecture:
- aiohttp HTTP server serving the teleop HTML page and the WebRTC signaling endpoint (`/offer`)
- aiortc `RTCPeerConnection` per client, attached to a `VideoStreamTrack` that pulls latest frame from the camera thread
- Same aiohttp server hosts a WebSocket at `/control` for joystick input and telemetry

### 3. YOLO inference: stays the same

Code using `from ultralytics import YOLO; model = YOLO('yolov8n.engine')` does not change. The model file location may need updating if the old Dockerfile staged it under a path tied to jetson-inference.

### 4. Pre-built TensorRT engine

If the previous setup built the engine at runtime, decide whether to:
- Bake it into the image at Docker build time (only valid if build host = deploy host same SKU), OR
- Build on first container run and cache to a mounted volume

Build command: `yolo export model=yolov8n.pt format=engine half=True device=0`

## Safety logic that must be present in the teleop server

Non-negotiable, regardless of how clean the rest is:

1. **Deadman timeout on the control WebSocket.** If no command received for 500 ms, force `drive(0, 0)`. A dropped Wi-Fi packet otherwise keeps the robot driving.
2. **Server-side input clamping.** `vx = max(-1, min(1, float(vx)))`. Never trust browser values.
3. **VL53L0X speed override.** Before sending velocity to motors:
   `vx = min(vx, max(0.0, (vl53_mm - 200) / 500))`
   The robot refuses to move forward into close obstacles regardless of joystick input. Tune the 200 and 500 numbers to Felix's stopping distance.
4. **Motor command rate limit.** Hardware-side: don't send I2C/GPIO commands faster than the motor controller can accept. Software-side: dedupe consecutive identical commands.

## docker run requirements

The container needs these at runtime (Dockerfile alone is insufficient):

```bash
docker run -it --rm \
  --runtime=nvidia \
  --network=host \
  --privileged \
  -v /tmp/argus_socket:/tmp/argus_socket \
  -v /etc/enctune.conf:/etc/enctune.conf \
  -v /etc/nv_tegra_release:/etc/nv_tegra_release \
  -v /dev:/dev \
  felix:latest
```

`/tmp/argus_socket` is required for CSI cameras via nvarguscamerasrc. `--network=host` simplifies WebRTC signaling and ICE.

## Host-level changes (outside Docker)

These belong in a setup script or systemd unit on the Jetson itself, not the container:

```bash
# Free ~865MB by killing desktop GUI
sudo systemctl set-default multi-user.target

# Max performance mode
sudo nvpmodel -m 0
sudo jetson_clocks

# Monitoring tool
sudo pip3 install -U jetson-stats
```

## Verification checklist after build

Run inside the new container:

```bash
# CUDA available to PyTorch
python3 -c "import torch; print(torch.cuda.is_available())"   # → True

# OpenCV built with GStreamer
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i gstreamer   # → YES

# NVIDIA GStreamer plugins visible
gst-inspect-1.0 nvarguscamerasrc | head -5   # → element details, not "No such element"

# Ultralytics versions
python3 -c "import ultralytics, onnxruntime; print(ultralytics.__version__, onnxruntime.__version__)"

# YOLO inference smoke test on TensorRT engine
yolo predict model=yolov8n.engine source=https://ultralytics.com/images/bus.jpg
```

If any of these fail, the issue is environment (base image, docker run flags), not application code, so debug in that order before touching Felix's own modules.

## What stays unchanged

- The ultralytics YOLO API (`YOLO(...).predict()`, `.track()`)
- I2C / GPIO sensor reading code via Adafruit Blinka
- Motor command code
- Any flask routes that don't touch video
- The training pipeline (if any) since torch is still present

## Suggested implementation order

1. Build the new Dockerfile and confirm verification checklist passes
2. Get cv2+GStreamer camera capture working in isolation, print FPS
3. Add aiortc WebRTC server, verify glass-to-glass latency on LAN
4. Add joystick WebSocket with the four safety items above
5. Re-integrate YOLO inference on the captured frames
6. Re-integrate VL53L0X reading and fuse with joystick clamping
7. Bake the TensorRT engine into the image (if appropriate) and ship