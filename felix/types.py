from abc import abstractmethod, ABC
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
import numpy as np
from numpy import ndarray
import time


@dataclass
class Measurement:
    id: int
    value: Any

    def __repr__(self):
        return f"tof id: {self.id} value: {self.value}"

    @property
    def dict(self):
        return {"id": self.id, "value": self.value}
    
    @classmethod
    def model_validate(cls, value: dict) -> 'Measurement':
        """Create Measurement from dictionary (similar to Pydantic)"""
        return cls(**value)


@dataclass
class DataModel(ABC):
    @property
    @abstractmethod
    def numpy(self) -> ndarray:
        pass


@dataclass
class Vector3(DataModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __post_init__(self):
        # Ensure values are floats
        self.x = float(self.x)
        self.y = float(self.y)
        self.z = float(self.z)

    def copy(self) -> 'Vector3':
        return Vector3(self.x, self.y, self.z)
    
    @property
    def dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_tuple(cls, tup) -> 'Vector3':
        x, y, z = tup
        return cls(x, y, z)

    @classmethod
    def from_numpy(cls, input_array: np.array) -> "Vector3":
        assert input_array.shape == (3,), f"expected np array with shape (3,) got array with shape {input_array.shape}"
        x, y, z = input_array
        return cls(x, y, z)

    @property
    def numpy(self) -> np.array:
        return np.array([self.x, self.y, self.z])

    @property
    def csv(self) -> str:
        return f"{self.x},{self.y},{self.z}"

    def __repr__(self):
        return f"[{self.x:.3f},{self.y:.3f},{self.z:.3f}]"


@dataclass
class Vector4(DataModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0

    @classmethod
    def from_numpy(cls, input_array: np.array) -> "Vector4":
        assert input_array.shape == (4,), f"expected np array with shape (4,) got array with shape {input_array.shape}"
        x, y, z, w = input_array
        return cls(x, y, z, w)

    @property
    def numpy(self) -> np.array:
        return np.array([self.x, self.y, self.z, self.w])

    @property
    def csv(self) -> str:
        return f"{self.x},{self.y},{self.z},{self.w}"  # Fixed: was using self.z twice

    def __repr__(self):
        return f"[{self.x:.3f},{self.y:.3f},{self.z:.3f},{self.w:.3f}]"

    @property
    def dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z, "w": self.w}


@dataclass
class Time(DataModel):
    sec: int = field(default_factory=lambda: int(time.time()))
    nanosec: int = field(default_factory=lambda: int(time.time() * 1_000_000_000))

    @property
    def numpy(self) -> np.array:
        return np.array([self.sec, self.nanosec])

    @property
    def dict(self) -> Dict[str, int]:
        return {"sec": self.sec, "nanosec": self.nanosec}


@dataclass
class Header:
    stamp: Time = field(default_factory=Time)
    frame_id: Optional[str] = None

    @property
    def dict(self) -> Dict[str, Any]:
        return {"stamp": self.stamp.dict, "frame_id": self.frame_id}
    
    def __repr__(self):
        return f"Header(stamp={self.stamp}, frame_id={self.frame_id})"


@dataclass
class Point(Vector3):
    """Point is just a Vector3 with semantic meaning"""
    pass


@dataclass
class Quaternion(Vector4):  # Fixed spelling: was "Quarternion"
    """Quaternion for representing rotations"""
    pass


@dataclass
class Twist(DataModel):
    linear: Vector3 = field(default_factory=Vector3)
    angular: Vector3 = field(default_factory=Vector3)

    def copy(self) -> 'Twist':
        return Twist(linear=self.linear.copy(), angular=self.angular.copy())
    
    @property
    def numpy(self) -> np.array:
        return np.concatenate((self.linear.numpy, self.angular.numpy))

    @property
    def csv(self) -> str:
        return f"{self.linear.csv},{self.angular.csv}"  # Fixed method calls

    @property
    def dict(self) -> Dict[str, Dict[str, float]]:
        return {"linear": self.linear.dict, "angular": self.angular.dict}
    
    @classmethod
    def model_validate(cls, value: Dict) -> 'Twist':
        """Create Twist from dictionary (similar to Pydantic)"""
        linear = Vector3(
            x=float(value["linear"]["x"]),
            y=float(value["linear"]["y"]),
            z=float(value["linear"].get("z", 0))
        )
        angular = Vector3(
            x=float(value["angular"].get("x", 0)),
            y=float(value["angular"].get("y", 0)),
            z=float(value["angular"]["z"])
        )
        return cls(linear=linear, angular=angular)

    @property
    def is_zero(self) -> bool:
        return self.linear.x == 0 and self.linear.y == 0 and self.angular.z == 0

    def __repr__(self):
        return f"Twist(linear={self.linear}, angular={self.angular})"


@dataclass
class Pose(DataModel):
    position: Point = field(default_factory=Point)
    orientation: Quaternion = field(default_factory=Quaternion)

    @property
    def csv(self) -> str:
        return f"{self.position.csv},{self.orientation.csv}"  # Fixed method calls

    @property
    def numpy(self) -> np.array:
        return np.concatenate((self.position.numpy, self.orientation.numpy))

    @property
    def dict(self) -> Dict[str, Dict[str, float]]:
        return {
            "position": self.position.dict,
            "orientation": self.orientation.dict,
        }
    
    def __repr__(self):
        return f"Pose(position={self.position}, orientation={self.orientation})"


@dataclass
class Odometry(DataModel):
    header: Header = field(default_factory=Header)
    child_frame_id: Optional[str] = None
    twist: Twist = field(default_factory=Twist)
    pose: Pose = field(default_factory=Pose)

    @property
    def numpy(self) -> np.array:
        return np.concatenate((self.twist.numpy, self.pose.numpy))  # Fixed concatenation

    @property
    def dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.dict,
            "child_frame_id": self.child_frame_id,
            "twist": self.twist.dict,
            "pose": self.pose.dict,
        }
    
    def __repr__(self) -> str:
        return f"Odometry(header={self.header}, child_frame_id={self.child_frame_id}, twist={self.twist}, pose={self.pose})"


# Example usage and helper functions
def create_sample_odometry() -> Odometry:
    """Create a sample odometry message for testing"""
    return Odometry(
        header=Header(
            stamp=Time(),
            frame_id="odom"
        ),
        child_frame_id="base_link",
        pose=Pose(
            position=Point(1.0, 2.0, 0.0),
            orientation=Quaternion(0.0, 0.0, 0.0, 1.0)
        ),
        twist=Twist(
            linear=Vector3(0.5, 0.0, 0.0),
            angular=Vector3(0.0, 0.0, 0.1)
        )
    )


def odometry_from_dict(data: Dict) -> Odometry:
    """Reconstruct Odometry from dictionary (useful for deserialization)"""
    header = Header(
        stamp=Time(**data["header"]["stamp"]),
        frame_id=data["header"]["frame_id"]
    )
    
    pose = Pose(
        position=Point(**data["pose"]["position"]),
        orientation=Quaternion(**data["pose"]["orientation"])
    )
    
    twist = Twist(
        linear=Vector3(**data["twist"]["linear"]),
        angular=Vector3(**data["twist"]["angular"])
    )
    
    return Odometry(
        header=header,
        child_frame_id=data["child_frame_id"],
        pose=pose,
        twist=twist
    )


if __name__ == "__main__":
    # Test the dataclasses
    print("Testing dataclass conversion...")
    
    # Create sample data
    odom = create_sample_odometry()
    print(f"Created odometry: {odom}")
    
    # Test serialization
    odom_dict = odom.dict
    print(f"Serialized to dict: {odom_dict}")
    
    # Test deserialization
    odom_reconstructed = odometry_from_dict(odom_dict)
    print(f"Reconstructed: {odom_reconstructed}")
    
    # Test numpy conversion
    print(f"Numpy array: {odom.numpy}")
    
    # Test individual components
    point = Point(1, 2, 3)
    print(f"Point: {point}")
    print(f"Point numpy: {point.numpy}")
    
    twist = Twist(linear=Vector3(1, 0, 0), angular=Vector3(0, 0, 0.5))
    print(f"Twist: {twist}")
    print(f"Is zero: {twist.is_zero}")