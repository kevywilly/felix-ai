import traitlets
from traitlets.config.configurable import SingletonConfigurable
from src.utils.image import Image, ImageUtils
from src.interfaces.msg import Odometry, Twist
from src.nodes.node import Node
from src.nodes.controller import Controller
from src.nodes.camera import Camera
import atexit


class Robot(Node):

    image = traitlets.Instance(Image)

    def __init__(self, *args, **kwargs):
        super(Robot, self).__init__(**kwargs)
        
        self.image = Image()

        self._camera: Camera = Camera()
        self._controller: Controller = Controller()

        self._controller.spin()
        self._camera.spin()
        
        self._setup_subscriptions()
        atexit.register(self._remove_subscriptions)


    def _setup_subscriptions(self):
        traitlets.dlink((self._camera, 'value'), (self.image, 'value'), transform=ImageUtils.bgr8_to_jpeg)
        self._controller.observe(self._motion_changed, names=["motion_data"])


    def _remove_subscriptions(self):
        self._camera.unobserve_all()
        self._controller.unobserve_all()

    def _motion_changed(self, changed):
        if changed.new != changed.old:
            self.logger.info(changed.new)
        

    def get_image(self):
        return self.image.value
    
    
    def set_nav_target(self, msg: Odometry):
        self._controller.nav_target=msg


    def set_cmd_vel(self, msg: Twist):
        self._controller.cmd_vel=msg




        
