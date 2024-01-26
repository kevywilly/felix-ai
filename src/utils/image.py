import traitlets
import cv2


class Image(traitlets.HasTraits):
    value = traitlets.Any()


class ImageUtils:

    @staticmethod
    def bgr8_to_jpeg(value, quality=75):
        try:
            return bytes(cv2.imencode('.jpg', value)[1])
        except:
            return None
    