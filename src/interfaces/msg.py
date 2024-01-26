from pydantic import BaseModel
from typing import Optional
import numpy as np
import time
    
class Vector3(BaseModel):
    x: Optional[float] = 0.0
    y: Optional[float] = 0.0
    z: Optional[float] = 0.0

    @classmethod
    def from_tuple(cls, tup):
        return Vector3(x=tup[0], y=tup[1], z=tup[2])

    @classmethod
    def from_numpy(cls, input: np.array) -> "Vector3":
        assert input.shape==(3,), f"expected np array with shape (3,) got array with shape {input.shape}"
        x,y,z = input
        return Vector3(x,y,z)

    def to_numpy(self):
        return np.array([self.x, self.y, self.z])
    
    def __repr__(self):
        return f'<vector x:{self.x} y:{self.y} z:{self.z}>'
    
    
class Vector4(BaseModel):
    x: Optional[float] = 0.0
    y: Optional[float] = 0.0
    z: Optional[float] = 0.0
    w: Optional[float] = 0.0

    @classmethod
    def from_numpy(cls, input: np.array) -> "Vector4":
        assert input.shape==(4,), f"expected np array with shape (3,) got array with shape {input.shape}"
        x,y,z,w = input
        return Vector4(x,y,z,w)
    
    def to_numpy(self):
        return np.array([self.x, self.y, self.z, self.w])

    def __repr__(self):
        return f'<vector x:{self.x} y:{self.y} z:{self.z} w:{self.w}>'

class Time(BaseModel):
    sec: Optional[int] = int(time.time())
    nanosec: Optional[int] = int(time.time()*(1000000000))


class Header(BaseModel):
    stamp: Optional[Time] = Time()
    frame_id: Optional[str] = None
    

class Point(Vector3):
    pass


class Quarternion(Vector4):
    pass


class Twist(BaseModel):
    linear: Optional[Vector3] = Vector3()
    angular: Optional[Vector3] = Vector3()
        

class Pose(BaseModel):
    position: Optional[Point] = Point()
    orientation: Optional[Quarternion] = Quarternion()


class Odometry(BaseModel):
    header: Optional[Header] = Header()
    child_frame_id: Optional[str] = None
    twist: Optional[Twist] = Twist()
    pose: Optional[Pose] = Pose()
