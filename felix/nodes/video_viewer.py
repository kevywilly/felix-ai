import traitlets
import atexit
import threading
import cv2
import logging

logger = logging.getLogger('VideoViewer')

class VideoViewer(traitlets.HasTraits):

    camera_image = traitlets.Any(allow_none=True)
    window_name = 'video'

    def __init__(self):
        atexit.register(self.shutdown)
        try:
            self.main_thread()
            logger.info("Started Video Viewer")
        except Exception as ex:
            logger.error(f"Failed to start Video Viewer\n: {ex.__str__()}")

    def display(self):
        try:
            img = cv2.resize(self.camera_image, (300,300), cv2.INTER_LINEAR)
            cv2.imshow(self.window_name, img)
        except:
            pass

    def main_thread(self):
        cv2.namedWindow(self.window_name)
        self.t = threading.Thread(target=self.display, name='display')
        self.t.setDaemon(True)
        self.t.start()
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def shutdown(self):
        self.t.join()
        cv2.destroyAllWindows()
  

        
