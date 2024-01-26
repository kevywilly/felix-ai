

class CameraSensorMode:
    def __init__(self, id: int, width: int, height: int, framerate: int):
        self.id = id
        self.width = width
        self.height = height
        self.framerate = framerate

    def to_nvargus_string(self, sensor_id: int=0):
        return "nvarguscamerasrc sensor_id={} sensor_mode={} ! video/x-raw(memory:NVMM), " \
                "width=(int){}, height=(int){}, format=(string)NV12, framerate=(fraction){}/1 ! " \
                "nvvidconv ! video/x-raw, format=(string)I420 ! appsink max-buffers=1 drop=true".format(
                sensor_id, 
                self.id,
                self.width, 
                self.height, 
                self.framerate
                )
    
