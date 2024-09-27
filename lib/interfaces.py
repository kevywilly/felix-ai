from abc import abstractmethod, ABC
from typing import Dict, Optional
import numpy as np
from numpy import ndarray
import time


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
    def __init__(self, linear=Vector3(0, 0, 0), angular=Vector3(0, 0, 0)):
        self.linear = linear
        self.angular = angular

    def copy(self):
        return Twist(linear=self.linear.copy(), angular=self.angular.copy())
    
    @property
    def numpy(self):
        return np.concatenate((self.linear.numpy, self.angular.numpy))

    @property
    def csv(self):
        return ",".join([self.linear.csv(), self.angular().csv()])

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
        position: Optional[Point] = Point(),
        orientation: Optional[Quarternion] = Quarternion(),
    ):
        self.position = position
        self.orientation = orientation

    @property
    def csv(self):
        return ",".join([self.position.csv(), self.orientation().csv()])

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
        header: Optional[Header] = Header(),
        child_frame_id: Optional[str] = None,
        twist: Optional[Twist] = Twist(),
        pose: Optional[Pose] = Pose(),
    ):
        self.header = header
        self.child_frame_id = child_frame_id
        self.twist = twist
        self.pose = pose

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
