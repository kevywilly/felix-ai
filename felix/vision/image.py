import cv2


class ImageUtils:

    @staticmethod
    def bgr8_to_jpeg(value, quality=75):
        try:
            return bytes(cv2.imencode('.jpg', value)[1])
        except:
            return None
        
    @staticmethod
    def bgr8_to_rgb8(cv2_img):
        return cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)

    @staticmethod
    def cv2_to_jpeg(cv2_img):
        return cv2.imencode('.jpg', cv2_img)

    @staticmethod
    def cv2_to_jpeg_bytes(cv2_img):
        return bytes(cv2.imencode('.jpg', cv2_img)[1])
    