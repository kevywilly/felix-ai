# Object Detection & Seeking — Setup & Runbook

This documents the YOLO object-detection + object-seeking feature and the exact
steps to get it running after a container rebuild.

**Why this file exists:** the repo (`/felix-ai`) and data (`/data`) are host-mounted
volumes, so they survive container rebuilds — but anything you `pip install` inside a
running container, and your terminal history, do not. Everything you need is here.

---

## What was added

- **Detection** — a `Detector` node runs Ultralytics **YOLO** on the camera feed
  (~8 Hz) and publishes bounding boxes on the `Topics.detections` signal. Perception
  only; it never drives.
- **Seeking** — an `ObjectSeeker` node locks onto the largest box of a chosen class
  and steers toward it, with a **ToF safety veto** (won't drive forward into an
  obstacle). Toggled from the web UI.
- **Base image change** — `docker/Dockerfile` now starts from
  `dustynv/jetson-inference:r36.4.0` (jetson_utils + PyTorch, no nano_llm/VILA).
  Video plumbing (`felix/agents/video_agent.py`) was rewritten onto `jetson_utils`
  directly. Ultralytics is installed `--no-deps` so it can't overwrite the base
  image's CUDA PyTorch.

Files changed are listed at the bottom.

---

## Step 1 — Rebuild the container (one time, after these code changes)

On the **host** (not inside a container):

```bash
cd ~/felix-ai
./docker/build.sh          # builds felix-ai:latest from the new Dockerfile
```

This installs `ultralytics`, `onnx`, and `onnxslim` into the image.

---

## Step 2 — Install the YOLO model (one time)

The model lives in **`model_root` = `/data/felix/models/`** (host: `~/data/felix/models`),
which persists across rebuilds. The `Detector` looks for, in order:

1. `/data/felix/models/yolov8n.engine`  ← TensorRT, fast (preferred)
2. `/data/felix/models/yolov8n.pt`      ← plain PyTorch (fallback)

If neither exists, the detector logs a warning and **safely disables itself**
(no detections, so Seek does nothing — it fails safe).

Pick ONE of the two options below.

### Option A — Quick start (`.pt`, no export)

Fastest way to a working demo. Plain PyTorch `yolov8n` keeps up fine at 8 Hz on the
Orin Nano 8GB.

```bash
mkdir -p ~/data/felix/models
wget -O ~/data/felix/models/yolov8n.pt \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

(You can run this on the host — it just downloads a file into the mounted volume.)

### Option B — TensorRT engine (faster, lower memory — recommended once it works)

The engine **must be built inside the container** so its TensorRT version matches
the one that loads it. An engine built anywhere else will not load.

```bash
cd ~/felix-ai
./scripts/start-container.sh         # opens a shell INSIDE the felix-ai container

# --- now you are inside the container ---
mkdir -p /data/felix/models
cd /data/felix/models
yolo export model=yolov8n.pt format=engine half=True device=0
#   ^ downloads yolov8n.pt here (needs internet), then writes yolov8n.engine here.
#   onnx + onnxslim are already baked into the image, so no extra pip install needed.
exit
```

Result: `/data/felix/models/yolov8n.engine`. The detector will prefer it automatically.

> If you ever see an export error about missing `onnx`, the image predates this
> change — rebuild (Step 1), or inside the container run `pip install onnx onnxslim`.

---

## Step 3 — Run the robot

On the host:

```bash
cd ~/felix-ai
./scripts/start-felix-ai.sh          # runs the container + app.py
```

Open the control panel at `http://<robot-host>` (port 80). The video feed comes from
`https://orin1:8554` (WebRTC, unchanged).

Confirm detection is alive: the container logs should show the `Detector` node
spinning and (if objects are in view) periodic detection activity. If you see
`Detector model ... not found, detector disabled`, revisit Step 2.

---

## Step 4 — Use Seek mode

In the control panel's button row:

1. Pick a target class in the **dropdown** (`person`, `chair`, `bottle`, `cup`,
   `sports ball`, `dog`, `cat`, `backpack`).
2. Press **`Seek On`**.

The robot turns to center the largest matching object and drives toward it, slowing
as it gets close. Enabling Seek automatically turns **AutoDrive off** (and vice
versa) — only one driver runs at a time. Any **stop** disengages Seek.

### Safety behavior (expected, not a bug)
- If the ToF sensors read an obstacle closer than `tof.threshold` in `config.yml`
  (default 200), the robot **rotates to keep the target centered but will not drive
  forward**. Back the obstacle away and it resumes.
- No matching object in view → it issues a single stop and waits.

**First test on blocks / a stand** before driving on the floor, and verify the ToF
stop by putting a hand in front of the sensors while it's seeking.

---

## How it works (data flow)

```
Camera ──raw_image──► Detector (YOLO/TensorRT) ──detections──► ObjectSeeker
                                                                   │ (+ ToF veto)
                                                                   ▼
                                              cmd_vel ──► Controller ──► mecanum ──► motors
```

- `Detector` (`felix/nodes/detector.py`) — `raw_image` → `Topics.detections`
  (`DetectionFrame` of normalized `[0,1]` boxes). Runs at 8 Hz.
- `ObjectSeeker` (`felix/nodes/object_seeker.py`) — picks the largest box matching
  `target_label`, converts its center to a steering `Twist` (same sign convention as
  click-to-navigate, scaled by `autodrive.linear`/`autodrive.angular` from
  `config.yml`), applies the ToF veto, and sends `Topics.cmd_vel`.
- `app.py` — instantiates both, spins them in the async loop, and wires the UI
  toggle + target selector with single-driver mutual exclusion.

Tuning lives in `config.yml`: seek speed = `autodrive.linear` / `autodrive.angular`;
ToF veto distance = `tof.threshold`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Log: `Detector ... not found, detector disabled` | No model at `/data/felix/models/`. Do Step 2. |
| Log: `ultralytics not importable` | Image wasn't rebuilt. Do Step 1. |
| `yolo export` errors about `onnx` | Old image. Rebuild (Step 1), or `pip install onnx onnxslim` in the container. |
| Engine fails to load / version mismatch | Engine built in a different TensorRT. Re-export inside the current container (Option B). |
| Seek does nothing | Detector has no model, the target class isn't in view, or AutoDrive is on (mutual exclusion). |
| Seek rotates but won't go forward | ToF veto active — obstacle within `tof.threshold`. Expected safety behavior. |
| Want more headroom / higher FPS | Switch from `.pt` (Option A) to a TensorRT `.engine` (Option B). |

---

## Files changed (reference)

- `docker/Dockerfile` — base image → `jetson-inference`; added `ultralytics`
  (`--no-deps`) + `onnx`/`onnxslim`.
- `felix/agents/video_agent.py` — rewritten onto `jetson_utils` (drops nano_llm).
- `felix/signals.py` — added `Topics.detections`.
- `lib/interfaces.py` — added `Detection` and `DetectionFrame`.
- `felix/nodes/detector.py` — new perception node.
- `felix/nodes/object_seeker.py` — new behavior node.
- `app.py` — instantiates/spins both; Seek UI toggle + target selector; mutual
  exclusion with AutoDrive.

> Dead code on the new base: `felix/nodes/video.py` and `felix/nodes/chat.py` still
> import `nano_llm` but are not loaded by `nodes/__init__.py` or `app.py`. Delete or
> guard them when convenient.

> Repo file ownership note: files under `~/felix-ai` should be owned by `orin:orin`.
> Models written into `/data` by the container are root-owned, which is fine for
> runtime.
