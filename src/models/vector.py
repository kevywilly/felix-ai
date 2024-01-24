import numpy as np
from abc import ABC
class ModelBase(ABC):
    def json(self):
        return self.__dict__
    
class Vector3(ModelBase):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @classmethod
    def from_numpy(cls, input: np.array) -> "Vector3":
        assert input.shape==(3,), f"expected np array with shape (3,) got array with shape {input.shape}"
        x,y,z = input
        return Vector3(x,y,z)

    def to_numpy(self):
        return np.array([self.x, self.y, self.z])
    
    def __repr__(self):
        return f'<vector x:{self.x} y:{self.y} z:{self.z}>'

class Vector4(ModelBase):
    def __init__(self, x=0.0, y=0.0, z=0.0, w=0.0):
        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)
        self.w:float  = float(w)

    @classmethod
    def from_numpy(cls, input: np.array) -> "Vector4":
        assert input.shape==(4,), f"expected np array with shape (3,) got array with shape {input.shape}"
        x,y,z,w = input
        return Vector4(x,y,z,w)
    
    def to_numpy(self):
        return np.array([self.x, self.y, self.z, self.w])

    def __repr__(self):
        return f'<vector x:{self.x} y:{self.y} z:{self.z} w:{self.w}>'

