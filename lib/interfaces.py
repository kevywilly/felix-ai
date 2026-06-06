from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
from numpy import ndarray
import time


class Measurement:
    def __init__(self, id: int, value: any):
        self.id = id
        self.value = value

    def __repr__(self):
        return f"tof: {self.id} range: {self.value}"

class DataModel(ABC):
    @property
    def numpy(self) -> ndarray:
        return np.array()


class Vector3(DataModel):
    def __init__(self, x: any = 0.0, y: any = 0.0, z: any = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def copy(self):
        return Vector3(self.x, self.y, self.z)
    
    @property
    def dict(self):
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_tuple(cls, tup):
        x, y, z = tup
        return Vector3(x, y, z)

    @classmethod
    def from_numpy(cls, input: np.array) -> "Vector3":
        assert input.shape == (
            3,
        ), f"expected np array with shape (3,) got array with shape {input.shape}"
        x, y, z = input
        return Vector3(x, y, z)

    @property
    def numpy(self):
        return np.array([self.x, self.y, self.z])

    @property
    def csv(self):
        return f"{self.x},{self.y},{self.z}"

    def __repr__(self):
        return f"[{self.x:.3f},{self.y:.3f},{self.z:.3f}]"


class Vector4(DataModel):
    def __init__(
        self,
        x: Optional[float] = 0.0,
        y: Optional[float] = 0.0,
        z: Optional[float] = 0.0,
        w: Optional[float] = 0.0,
    ):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    @classmethod
    def from_numpy(cls, input: np.array) -> "Vector4":
        assert input.shape == (
            4,
        ), f"expected np array with shape (3,) got array with shape {input.shape}"
        x, y, z, w = input
        return Vector4(x, y, z, w)

    @property
    def numpy(self):
        return np.array([self.x, self.y, self.z, self.w])

    @property
    def csv(self):
        return f"{self.x},{self.y},{self.z},{self.z}"

    def __repr__(self):
        return f"[{self.x:.3f},{self.y:.3f},{self.z:.3f},{self.w:.3f}]"

    @property
    def dict(self):
        return {"x": self.x, "y": self.y, "z": self.z, "w": self.w}


class Time(DataModel):
    def __init__(
        self,
        sec: Optional[int] = int(time.time()),
        nanosec: Optional[int] = int(time.time() * (1000000000)),
    ):
        self.sec = sec
        self.nanosec = nanosec

    @property
    def numpy(self):
        return np.array([self.sec, self.nanosec])

    @property
    def dict(self):
        return {"sec": self.sec, "nanosec": self.nanosec}


class Header:
    def __init__(self, stamp: Optional[Time] = Time(), frame_id: Optional[str] = None):
        self.stamp = stamp
        self.frame_id = frame_id

    @property
    def dict(self):
        return {"stamp": self.stamp.dict, "frame_id": self.frame_id}
    
    def __repr__(self):
        return f"Header(stamp={self.stamp}, frame_id={self.frame_id})"


class Point(Vector3):
    pass


class Quarternion(Vector4):
    pass


class Twist(DataModel):
    def __init__(self, linear=None, angular=None):
        # NB: do not default to shared Vector3() instances. Mutable default
        # arguments are evaluated once, so every bare Twist() would alias the
        # same linear/angular vectors -- mutating one ``Twist().linear.x`` then
        # corrupts every other "zero" Twist (including stop commands).
        self.linear = linear if linear is not None else Vector3(0, 0, 0)
        self.angular = angular if angular is not None else Vector3(0, 0, 0)

    def copy(self):
        return Twist(linear=self.linear.copy(), angular=self.angular.copy())
    
    @property
    def numpy(self):
        return np.concatenate((self.linear.numpy, self.angular.numpy))

    @property
    def csv(self):
        return ",".join([self.linear.csv, self.angular.csv])

    @property
    def dict(self):
        return {"linear": self.linear.dict, "angular": self.angular.dict}
    
    @classmethod
    def model_validate(cls, value: Dict):
        t = Twist()
        t.linear.x = float(value["linear"]["x"])
        t.linear.y = float(value["linear"]["y"])
        t.angular.z = float(value["angular"]["z"])
        return t

    @property
    def is_zero(self):
        return self.linear.x == 0 and self.linear.y == 0 and self.angular.z == 0

    def __repr__(self):
        return f"[[{self.linear}],[{self.angular}]]"


class Pose(DataModel):
    def __init__(
        self,
        position: Point | None = None,
        orientation: Quarternion | None = None,
    ):
        self.position = position or Point()
        self.orientation: Quarternion = orientation or Quarternion()

    @property
    def csv(self):
        return ",".join([self.position.csv, self.orientation.csv])

    @property
    def numpy(self):
        return np.concatenate((self.position.numpy, self.orientation.numpy))

    @property
    def dict(self):
        return {
            "position": self.position.dict,
            "orientation": self.orientation.dict,
        }
    
    def __repr__(self):
        return f"Pose(position={self.position}, orientation={self.orientation})"


class Odometry(DataModel):
    def __init__(
        self,
        header: Header | None = None,
        child_frame_id: str | None = None,
        twist: Twist | None = None,
        pose: Pose | None = None,
    ):
        self.header: Header = header or Header()
        self.child_frame_id: str | None = child_frame_id
        self.twist: Twist = twist or Twist()
        self.pose: Pose = pose or Pose()

    @property
    def numpy(self):
        return np.concatenate(self.twist.numpy, self.pose.numpy)

    @property
    def dict(self):
        return {
            "header": self.header.dict,
            "child_frame_id": self.child_frame_id,
            "twist": self.twist.dict,
            "pose": self.pose.dict,
        }
    
    def __repr__(self) -> str:
        return f"Odometry(header={self.header}, child_frame_id={self.child_frame_id}, twist={self.twist}, pose={self.pose})"


@dataclass
class SensorReading:
    id: int
    type: str
    value: float
    ts: int

    @staticmethod
    def from_json(data) -> "SensorReading":
        return SensorReading(
            id=data.get("id"),
            type=data.get("type"),
            value=data.get("value"),
            ts=data.get("ts", int(time.time()))
        )
    
    def __str__(self):
        return (f"SensorReading(id={self.id}, type={self.type}, "
                f"value={self.value}, ts={self.ts})")
    
@dataclass
class Prediction:
    source: str
    left: float
    right: float
    forward: float
    ts: int = lambda: int(time.time())

    def __str__(self):
        return (f"Prediction(source={self.source}, left={self.left}, "
                f"right={self.right}, forward={self.forward}, ts={self.ts})")


@dataclass
class Detection:
    """A single detected object. Box corners are normalized to [0,1]."""
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    @property
    def dict(self):
        return {
            "label": self.label,
            "confidence": self.confidence,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }

    def __str__(self):
        return (f"Detection(label={self.label}, conf={self.confidence:.2f}, "
                f"box=[{self.x1:.3f},{self.y1:.3f},{self.x2:.3f},{self.y2:.3f}])")


@dataclass
class DetectionFrame:
    """All detections from one frame, plus the source frame dimensions."""
    detections: list
    width: int
    height: int
    ts: int

    @property
    def dict(self):
        return {
            "detections": [d.dict for d in self.detections],
            "width": self.width,
            "height": self.height,
            "ts": self.ts,
        }
