from abc import abstractmethod, ABC
from typing import Optional
import numpy as np
from numpy import ndarray
import time


class DataModel(ABC):
    @abstractmethod
    def numpy() -> ndarray:
        return np.array()


class Vector3(DataModel):
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z

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

    def numpy(self):
        return np.array([self.x, self.y, self.z])

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

    def numpy(self):
        return np.array([self.x, self.y, self.z, self.w])

    def csv(self):
        return f"{self.x},{self.y},{self.z},{self.z}"

    def __repr__(self):
        return f"[{self.x:.3f},{self.y:.3f},{self.z:.3f},{self.w:.3f}]"

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

    def numpy(self):
        return np.array([self.sec, self.nanosec])

    def dict(self):
        return {"sec": self.sec, "nanosec": self.nanosec}


class Header:
    def __init__(self, stamp: Optional[Time] = Time(), frame_id: Optional[str] = None):
        self.stamp = stamp
        self.frame_id = frame_id

    def dict(self):
        return {"stamp": self.stamp, "frame_id": self.frame_id}


class Point(Vector3):
    pass


class Quarternion(Vector4):
    pass


class Twist(DataModel):
    def __init__(self, linear=Vector3(0, 0, 0), angular=Vector3(0, 0, 0)):
        self.linear = linear
        self.angular = angular

    def numpy(self):
        return np.concatenate((self.linear.numpy, self.angular.numpy))

    def csv(self):
        return ",".join([self.linear.csv(), self.angular().csv()])

    def dict(self):
        return {"linear": self.linear.dict(), "angular": self.angular.dict()}

    def is_zero(self):
        return self.linear.x == 0 and self.linear.y == 0 and self.angular.z == 0

    def __repr__(self):
        return f"[[{self.linear}],[{self.angular}]]"


class Pose(DataModel):
    def __init__(
        self,
        position: Optional[Point] = Point(),
        orientation: Optional[Quarternion] = Quarternion(),
    ):
        self.position = position
        self.orientation = orientation

    def csv(self):
        return ",".join([self.position.csv(), self.orientation().csv()])

    def numpy(self):
        return np.concatenate((self.position.numpy, self.orientation.numpy))

    def dict(self):
        return {
            "position": self.position.dict(),
            "orientation": self.orientation.dict(),
        }


class Odometry(DataModel):
    def __init__(
        self,
        header: Optional[Header] = Header(),
        child_frame_id: Optional[str] = None,
        twist: Optional[Twist] = Twist(),
        pose: Optional[Pose] = Pose(),
    ):
        self.header = header
        self.child_frame_id = child_frame_id
        self.twist = twist
        self.pose = pose

    def numpy(self):
        return np.concatenate(self.twist.numpy(), self.pose.numpy())

    def dict(self):
        return {
            "header": self.header.dict(),
            "child_frame_id": self.child_frame_id,
            "twist": self.twist.dict(),
            "pose": self.pose.dict(),
        }
