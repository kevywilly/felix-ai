# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Felix is an autonomous mobile robot running on an **NVIDIA Jetson Orin Nano** (ARM64/Tegra). The codebase drives a 4-wheel **mecanum** robot: it streams video from a CSI camera, accepts joystick/web control, collects labeled images, trains a PyTorch obstacle-avoidance CNN, and runs that model on-device for autonomous driving. The host CPython here is the runtime — there is no separate compile step.

## Running

The app is designed to run **inside a Docker container** on the Jetson, mounting the repo at `/felix-ai` and data at `/data`.

```bash
./docker/build.sh                              # build felix-ai:latest (uses host networking)
./scripts/start-felix-ai.sh                    # run container + launch app.py via /felix.sh
./scripts/start-container.sh                   # interactive shell in the container
python3 app.py                                 # run the app directly (inside container)
```

`app.py` is the entry point. It serves a **NiceGUI** web control panel on port **80**, spins the async nodes (`controller`, `pico`, `autodrive`), and runs a WebRTC video stream (`VideoStream`) on a background thread. The UI embeds the camera feed from `https://orin1:8554`.

Hardware is reached through fixed device symlinks created by udev rules (see `SETUP.md`, `docker/rules/`): `/dev/myserial` (Yahboom/Rosmaster motor controller, CH341 USB-serial), `/dev/mypico` (Raspberry Pi Pico sensors, 115200 baud), plus `/dev/i2c-*` and `/dev/video*`. Running outside the Jetson without these devices will fail at node construction (serial open, camera init).

## Training

```bash
./train.py [EPOCHS] --lr 0.001 --start-clean   # train ROI obstacle-avoidance model (click CLI)
./train_mecanum.sh                             # python3 -m felix.training.mecanum.train
```

`train.py` runs `ROIObstacleTrainer`. Training mode is set by `config.yml` → `training.mode` (`binary` / `ternary` / `mecanum`), which determines the number of output categories (2/3/5) and the labels. Models, checkpoints, and training images live under `/data/felix` (the `data_root` configured in `config.yml`).

## Tests

There is no test runner config; tests use plain pytest and live in `test/`.

```bash
pytest test/test_autodriver_model_path.py      # run the one real regression suite
pytest test/ -k autodriver                      # run a single test by name
```

Note: most files in `test/` are **manual hardware bring-up scripts** (`test-motors.py`, `gpio_test.py`, `motor_calibration.py`, `lidar.py`), not automated tests — they touch real devices. Only `test_autodriver_model_path.py` is a true unit/regression test.

## Architecture

### Node + signal model (the core pattern)

The system is a set of **nodes** wired together by **in-process pub/sub signals** — a lightweight, ROS-like design with no actual ROS dependency.

- **`lib/nodes/base.py` → `BaseNode`**: abstract base. Subclasses implement `spinner()` (one tick of work). `await node.spin(hz)` runs `spinner()` in a loop at a fixed frequency; `app.py` gathers several `spin()` coroutines with `asyncio.gather`. `atexit` triggers `shutdown()`.
- **`felix/signals.py` → `Topics`**: all cross-node communication. Each topic is a `blinker.signal` (e.g. `cmd_vel`, `raw_image`, `prediction`, `autodrive`, `nav_capture`, `pico_sensors`). Producers call `Topics.<name>.send(sender, payload=...)`; consumers `Topics.<name>.connect(handler)` in their `__init__`. **To trace any data flow, follow the topic**, not direct method calls between nodes.

Example flow: joystick move → `Joystick.get_twist()` → `Topics.cmd_vel.send(twist)` → `Controller._on_cmd_vel_signal` → vehicle kinematics → Rosmaster serial write to motors.

### Key nodes (`felix/nodes/`)

- **`controller.py` (`Controller`)**: owns the `Rosmaster` motor controller. Subscribes to `cmd_vel`, `stop`, `nav_target`, `nav_capture`, `pico_sensors`. Converts `Twist` → scaled wheel commands via the vehicle model and writes to `/dev/myserial`.
- **`camera.py` (`Camera`)**: reads CSI camera via an nvargus GStreamer pipeline (OpenCV `VideoCapture`), undistorts using calibration from `config.yml`, publishes frames on `Topics.raw_image`.
- **`autodriver.py` (`AutoDriver` → `TernaryObstacleAvoider` / `BinaryObstacleAvoider`)**: loads the trained torchvision model onto CUDA, runs inference on ROI-cropped frames, publishes `Topics.prediction`, and issues `cmd_vel` to avoid obstacles. Toggled on/off via `Topics.autodrive`.
- **`pico.py` (`PicoSensors`)**: reads JSON sensor lines (ToF/IR) from `/dev/mypico`, publishes `Topics.pico_sensors`.
- **`robot.py` (`Robot`)**: holds the latest JPEG frame and brokers image **snapshot/tag collection** for building training datasets (via `ImageCollector`).

### Vehicle kinematics (`lib/vehicles/`)

`Vehicle` (abstract) → `MecanumVehicle`. Holds physical constants (wheel radius, track width, gear ratio, RPM limits from `config.yml` → `vehicle:`) and the forward/inverse kinematics and `IK_MATRIX` that map a `Twist` (linear x/y + angular z) to four wheel velocities. This is where body-frame velocity becomes motor commands.

### Shared data types (`lib/interfaces.py`)

Hand-rolled, ROS-message-shaped types: `Vector3`, `Twist`, `Pose`, `Odometry`, `Header`, plus `SensorReading` and `Prediction`. They are **not** pydantic models despite pydantic being a dependency — each exposes `.dict`, `.numpy`, and `.csv`. `Twist.model_validate(dict)` parses incoming JSON. Prefer reusing these over inventing new payload shapes for signals.

### Configuration (`config.yml` + `felix/settings.py`)

`felix/settings.py` builds a single global `settings = AppSettings("/felix-ai/config.yml")` imported everywhere. **The config path is hardcoded to `/felix-ai/config.yml`** (with a fallback to a relative `config.yml`), matching the container mount. The loader registers a custom `!join` YAML tag used to compose data paths. `settings` constructs the `MecanumVehicle`, camera calibration matrices, ROI/model settings, and `TrainingConfig`. Changing robot behavior usually means editing `config.yml`, not code.

### The ROI model-path invariant (read before touching paths)

When `model.use_roi` is true, `settings.model_file` gets a `roi_` filename prefix and **diverges** from `settings.TRAINING.training_model_path`. The trainer writes to `settings.model_file`; inference drivers must load the **same** path. A past bug loaded the wrong (pre-ROI) path, feeding ROI-cropped frames to a stale model and locking the robot into a continuous spin. `test/test_autodriver_model_path.py` pins this invariant — do not break it.

## Layout notes

- `lib/` is the hardware/robotics-agnostic core (nodes base, interfaces, vehicles, Rosmaster driver, mocks in `lib/mock/`). `felix/` is the application (nodes, vision, motion, training, settings, signals).
- `pico-sensors-app/` is **MicroPython firmware** for the Pico (runs on the microcontroller, not the Jetson).
- `extras/` (notebooks, LLM experiments), `adafruit/`, `pinmux/`, `install/` are auxiliary/experimental.
- `old_train.py`, `nav_trainer.py` are legacy/auxiliary training scripts kept alongside the current `train.py`.
- Setup of the Jetson host (drivers, swap, GPIO overlays, jetson-containers) is documented in `SETUP.md`; camera sensor modes in `CAMERA.md`.
