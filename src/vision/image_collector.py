import os
import time
from pathlib import Path
import cv2
from settings import settings
from uuid import uuid4

class ImageCollector:
    def __init__(self):
        self.counts = {}
        self._make_folders()
        

    def _make_folders(self):
        try:
            os.makedirs(settings.TRAINING.tags_path)
        except FileExistsError:
            pass

        try:
            os.makedirs(settings.TRAINING.navigation_path)
        except FileExistsError:
            pass


    
    def save_image(self, image, path, filename) -> bool:
        
        if not os.path.exists(path=path):
            os.makedirs(path)

        save_path = os.path.join(path, filename)

        with open(save_path, 'wb') as f:
            print(f"writing image to {save_path}")
            try:
                f.write(image)
            except Exception as ex:
                print(ex)
                return False
        
        return save_path


    @classmethod
    def filetime(cls, extension=None) -> bool:
        s = str(time.time()).replace('.','-')
        if extension:
            return s+"."+extension
        return s
    
    def create_snapshot(self, image, folder, label) -> int:
        path = os.path.join(settings.TRAINING.training_folder(folder),label)
        self.save_image(
            image, 
            path, 
            self.filetime('jpg')
            )
        return self.get_snapshots(folder)
    
    def get_snapshots(self, folder):
        d = {}
        path = settings.TRAINING.training_folder(folder)
        if not os.path.exists(path):
            os.makedirs(path)
        for p in os.listdir(path):
            d[p.lower()] = len(os.listdir(os.path.join(path,p)))
        return d
    
    def save_tag(self, image, tag) -> int:
        self.save_image(image, os.path.join(settings.TRAINING.tags_path,tag.lower()), self.filetime('jpg'))
        return self.get_tags()

    def get_tags(self):
        d = {}
        
        for p in os.listdir(settings.TRAINING.tags_path):
            d[p.lower()] = len(os.listdir(os.path.join(settings.TRAINING.tags_path,p)))
        return d
            
    def save_navigation_image(self, x: int, y:int, width:int, height: int, image) -> str:
        name = 'xy_%03d_%03d_%03d_%03d_%s' % (x, y, width, height, self.filetime('jpg'))
        return self.save_image(
            image=image,
            path=settings.TRAINING.navigation_path,
            filename=name
        )


    def get_images(self, category):
        paths = sorted(Path(self.category_path(category)).iterdir(), key=os.path.getctime)
        return [p.name for p in paths]

    def load_image(self, category, name):
        im = cv2.imread(os.path.join(self.category_path(category), name), cv2.IMREAD_ANYCOLOR)
        _, im_bytes_np = cv2.imencode('.jpeg', im)

        return im_bytes_np.tobytes()

    def delete_image(self, category, name):
        try:
            os.remove(os.path.join(self.category_path(category), name))
            self._generate_counts()
        except:
            pass
            

        return True