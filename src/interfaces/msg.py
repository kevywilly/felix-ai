
from abc import abstractmethod
from pydantic import BaseModel
from typing import Optional
import numpy as np
from numpy import ndarray
import time

class DataModel(BaseModel):
    @abstractmethod
    def numpy() -> ndarray:
        return np.array()
    
    
class Vector3(DataModel):
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

    def numpy(self):
        return np.array([self.x, self.y, self.z])
    
    def csv(self):
        return f'{self.x},{self.y},{self.z}'
    
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
    
    def numpy(self):
        return np.array([self.x, self.y, self.z, self.w])
    
    def csv(self):
        return f'{self.x},{self.y},{self.z},{self.z}'

    def __repr__(self):
        return f'<vector x:{self.x} y:{self.y} z:{self.z} w:{self.w}>'

class Time(BaseModel):
    sec: Optional[int] = int(time.time())
    nanosec: Optional[int] = int(time.time()*(1000000000))
    def numpy(self):
        return np.array([self.sec,self.nanosec])


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

    def numpy(self):
        return np.concatenate((self.linear.numpy,self.angular.numpy))
    
    def csv(self):
        return ",".join([self.linear.csv(),self.angular().csv()])
        

class Pose(BaseModel):
    position: Optional[Point] = Point()
    orientation: Optional[Quarternion] = Quarternion()

    def csv(self):
        return ",".join([self.position.csv(),self.orientation().csv()])
    
    def numpy(self):
        return np.concatenate((self.position.numpy,self.orientation.numpy))


class Odometry(BaseModel):
    header: Optional[Header] = Header()
    child_frame_id: Optional[str] = None
    twist: Optional[Twist] = Twist()
    pose: Optional[Pose] = Pose()

    def numpy(self):
        return np.concatenate(self.twist.numpy(),self.pose.numpy())
