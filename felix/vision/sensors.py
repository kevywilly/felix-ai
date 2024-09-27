class CameraSensor:
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
    

    @classmethod
    def modes(cls):
        return [
            cls(0,3264,2464,21),
            cls(1,3264,1848,28),
            cls(2,1928,1080,29),
            cls(3,1640,1232,29),
            cls(4,1280,720,59),
            cls(5,1280,720,120)
        ]

    @classmethod
    def mode(cls, index):
        return cls.modes()[index]