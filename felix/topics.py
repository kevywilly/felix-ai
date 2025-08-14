from enum import Enum

class Topics(str, Enum):
    CMD_VEL = "cmd_vel"
    JOYSTICK = "joystick"
    NAV_TARGET = "nav_target"
    RAW_IMAGE = "raw_image"
    AUTODRIVE = "autodrive"
    STOP = "stop"
    IMAGE_TENSOR = "image_tensor"
    TOF = "tof"
