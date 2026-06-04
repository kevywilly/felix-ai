import asyncio
import logging
import threading
import time

import cv2
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

from felix.settings import settings
from felix.signals import Topics

logger = logging.getLogger(__name__)


def _build_gst_pipeline(sensor_id, in_w, in_h, fps, out_w, out_h):
    """nvargus CSI -> downscaled BGR appsink.

    ``drop=1 max-buffers=1`` is critical: the appsink only ever holds the most
    recent frame, so a slow consumer can never build up a latency backlog.
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={in_w}, height={in_h}, "
        f"format=NV12, framerate={fps}/1 ! "
        # flip-method=2 = 180deg rotation: the camera is mounted upside down.
        # Done here (hardware-accelerated) so the WebRTC view AND the frames
        # published on Topics.raw_image for the model/detector are all upright.
        f"nvvidconv flip-method=2 ! "
        f"video/x-raw, width={out_w}, height={out_h}, format=BGRx ! "
        "videoconvert ! video/x-raw, format=BGR ! "
        "appsink drop=1 max-buffers=1"
    )


class CameraCapture:
    """Background thread that keeps only the latest CSI frame.

    Replaces the old ``jetson_utils.videoSource`` capture. A single thread
    continuously pulls frames and (a) stashes the most recent one for the
    WebRTC track to read on demand and (b) republishes it on
    ``Topics.raw_image`` for the autodrive classifier, detector and snapshot
    collector. Consumers never pull frames on their own timing.
    """

    def __init__(self, sensor_id=0, out_w=960, out_h=540):
        mode = settings.DEFAULT_SENSOR_MODE
        self._pipeline = _build_gst_pipeline(
            sensor_id, mode.width, mode.height, mode.framerate, out_w, out_h
        )
        self._cap = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self, attempts=5, backoff=2.0):
        """Open the CSI camera, retrying on transient argus contention.

        The CSI camera allows only one argus consumer at a time, and argus
        needs a moment to release the sensor after a previous process exits.
        Restarting the app too soon after a prior run would otherwise fail the
        single ``VideoCapture`` open and kill the whole video thread. Retry a
        few times with backoff so that release window is tolerated.
        """
        for attempt in range(1, attempts + 1):
            self._cap = cv2.VideoCapture(self._pipeline, cv2.CAP_GSTREAMER)
            if self._cap.isOpened():
                break
            self._cap.release()
            self._cap = None
            if attempt < attempts:
                logger.warning(
                    "CSI camera busy (attempt %d/%d), retrying in %.1fs",
                    attempt, attempts, backoff,
                )
                time.sleep(backoff)
        else:
            raise RuntimeError(
                "Could not open CSI camera via GStreamer after "
                f"{attempts} attempts (camera held by another process?). "
                f"Pipeline:\n{self._pipeline}"
            )
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("CameraCapture started")

    def _loop(self):
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                logger.warning("CameraCapture: empty frame")
                continue
            with self._lock:
                self._frame = frame
            Topics.raw_image.send(self, payload=frame)

    def latest(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._cap is not None:
            self._cap.release()


class CameraTrack(VideoStreamTrack):
    """aiortc media track that serves the camera's latest frame.

    Draws YOLO detection boxes on the outgoing WebRTC copy only. The frames
    published on Topics.raw_image (model/detector input) are never touched
    because camera.latest() hands back a fresh copy.
    """

    def __init__(self, camera: CameraCapture, fallback=(540, 960)):
        super().__init__()
        self._camera = camera
        self._blank = np.zeros((*fallback, 3), dtype=np.uint8)
        self._detections = None
        # Keep a strong ref so blinker's default weak connection isn't GC'd.
        self._on_detections_ref = self._on_detections
        Topics.detections.connect(self._on_detections_ref)

    def _on_detections(self, sender, payload=None):
        self._detections = payload

    def _draw_boxes(self, frame):
        det = self._detections
        if det is None or not det.detections:
            return frame
        h, w = frame.shape[:2]
        for d in det.detections:
            x1, y1 = int(d.x1 * w), int(d.y1 * h)
            x2, y2 = int(d.x2 * w), int(d.y2 * h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{d.label} {d.confidence * 100:.0f}%"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            bh = th + 6
            # Put the label above the box, or just inside the top edge when
            # there's no room above (object near the top of the frame) -- else
            # the label is drawn at a negative y and clipped off-screen.
            ytop = y1 - bh if y1 - bh >= 0 else y1
            x = max(x1, 0)
            cv2.rectangle(frame, (x, ytop), (x + tw + 4, ytop + bh), (0, 255, 0), -1)
            cv2.putText(frame, label, (x + 2, ytop + th + 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        return frame

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self._camera.latest()
        if frame is None:
            frame = self._blank
        else:
            frame = self._draw_boxes(frame)
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


# Minimal receive-only WebRTC viewer. RTCPeerConnection works in a non-secure
# (http) context as long as we never call getUserMedia, so this is served over
# plain http and embedded by app.py's iframe.
_VIEWER_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Felix</title>
<style>html,body{margin:0;padding:0;background:#333;height:100%;overflow:hidden}
video{width:100%;height:100%;object-fit:contain;background:#333}
#s{position:absolute;top:6px;left:6px;font:12px monospace;color:#0f0;
   background:rgba(0,0,0,.5);padding:2px 6px;border-radius:3px;z-index:9}</style>
</head>
<body>
<video id="v" autoplay playsinline muted></video>
<div id="s">init</div>
<script>
const v = document.getElementById('v');
const s = document.getElementById('s');
// Show status only while connecting or on failure; hide once frames play so
// the overlay doesn't sit on top of a working image.
const log = (m) => { s.textContent = m; s.style.display = (m === 'playing') ? 'none' : 'block'; };
// In a cross-origin iframe, muted autoplay can still be blocked; play()
// explicitly and, if rejected, let a tap/click start it. The status overlay
// surfaces ICE/track/play failures that are otherwise invisible when embedded.
async function play() {
  try { await v.play(); log('playing'); }
  catch (e) { log('tap to play: ' + e.name); }
}
v.addEventListener('loadedmetadata', play);
document.body.addEventListener('click', () => v.play());
async function start() {
  try {
    const pc = new RTCPeerConnection();
    pc.oniceconnectionstatechange = () => log('ice: ' + pc.iceConnectionState);
    pc.addTransceiver('video', {direction: 'recvonly'});
    pc.ontrack = (e) => { v.srcObject = e.streams[0]; log('track'); };
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    const res = await fetch('/offer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sdp: pc.localDescription.sdp, type: pc.localDescription.type})
    });
    if (!res.ok) { log('offer HTTP ' + res.status); return; }
    await pc.setRemoteDescription(await res.json());
  } catch (e) { log('error: ' + e.message); }
}
start();
</script>
</body>
</html>
"""


class VideoStream:
    """CSI camera -> WebRTC (aiortc) on port 8554, and publishes each frame as a
    BGR numpy array on ``Topics.raw_image`` for the rest of the system.

    Drop-in replacement for the previous ``jetson_utils`` based implementation:
    same ``run()`` / ``shutdown()`` interface so ``app.py`` keeps starting it on
    a background thread.
    """

    def __init__(
        self,
        sensor_id: int = 0,
        port: int = 8554,
        video_output_width: int = 960,
        video_output_height: int = 540,
        **_legacy_kwargs,  # tolerate old call sites passing video_input/etc.
    ):
        self.port = port
        self.camera = CameraCapture(
            sensor_id=sensor_id,
            out_w=video_output_width,
            out_h=video_output_height,
        )
        self._pcs: set[RTCPeerConnection] = set()
        self._loop = None
        self._runner = None
        self._running = False

    async def _index(self, request):
        return web.Response(text=_VIEWER_HTML, content_type="text/html")

    async def _offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        self._pcs.add(pc)

        @pc.on("connectionstatechange")
        async def _on_state_change():
            logger.info("WebRTC connection state: %s", pc.connectionState)
            if pc.connectionState in ("failed", "closed"):
                await pc.close()
                self._pcs.discard(pc)

        pc.addTrack(CameraTrack(self.camera))

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.json_response(
            {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            }
        )

    async def _serve(self):
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_post("/offer", self._offer)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info("%s - WebRTC server ready on :%d", type(self).__name__, self.port)

        # Idle until shutdown() flips the flag.
        while self._running:
            await asyncio.sleep(0.5)

        for pc in list(self._pcs):
            await pc.close()
        self._pcs.clear()
        await self._runner.cleanup()

    def run(self, timeout=None):
        """Start capture + WebRTC server. Blocks (run on a background thread)."""
        self.camera.start()
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            self.camera.stop()
            self._loop.close()
        return self

    def shutdown(self):
        self._running = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    VideoStream().run()
