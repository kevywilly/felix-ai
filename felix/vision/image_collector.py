import os
import time
import json
from pathlib import Path
import cv2
from felix.settings import settings
from typing import Optional, Dict
from glob import glob

from lib.interfaces import Twist

def _normalize_velocity(value: float, scale: float = 100.0) -> int:
    return int(round(value, 2) * scale)

def _denormalize_velocity(value: int, scale: float = 100.0) -> float:
    return float(value) / scale

class ImageCollector:
    def __init__(self):
        self.counts = {}
        self._make_folders()
        

    def _make_folders(self):
        try:
            os.makedirs(settings.TRAINING.tags_path, exist_ok=True)
        except FileExistsError:
            pass

        try:
            os.makedirs(settings.TRAINING.navigation_path)
        except FileExistsError:
            pass

    
    def save_dict(self, data, path, filename) -> bool | str:
        if not os.path.exists(path=path):
            os.makedirs(path)

        save_path = os.path.join(path,filename)

        with open(save_path, 'w') as f:
            print(f"writing additional data to {save_path}")
            try:
                f.write(json.dumps(data))
                
            except Exception as ex:
                print(str(ex))
                return False

        return save_path
    
    def save_image(self, image, path, filename) -> bool | str:
        
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
    def time_prefix(cls) -> str:
        return str(int(time.time()*1000))
    
    @classmethod
    def filetime(cls, extension=None) -> str:
        s = cls.time_prefix()
        if extension:
            return s+"."+extension
        return s
    
    def create_snapshot(self, image, folder, label, additional_data: Optional[Dict] = None) -> dict:
        path = os.path.join(settings.TRAINING.training_folder(folder),label)
        t = self.time_prefix()
        self.save_image(
            image, 
            path, 
            f"{t}_image.jpg"
            )
        
        if additional_data:
            for k,v in additional_data.items():
                self.save_dict(v, path, f"{t}_{k}.json")
        
        return self.get_snapshots(folder)
    
    def get_snapshots(self, folder):
        d = {}
        path = settings.TRAINING.training_folder(folder)
        if not os.path.exists(path):
            os.makedirs(path)
        for p in os.listdir(path):
            d[p.lower()] = len(glob(os.path.join(path,p,"*.jpg")))
        return d
    
    def save_tag(self, image, tag, additional_data: Optional[Dict] = None) -> dict:

        path = os.path.join(settings.TRAINING.tags_path,tag.lower())
        t = self.time_prefix()

        self.save_image(image, path, f"{t}_image.jpg")

        if additional_data:
            for k,v in additional_data.items():
                self.save_dict(v, path, f"{t}_{k.lower()}.json")

        return self.get_tags()

    def get_tags(self):
        d = {}
        
        for p in os.listdir(settings.TRAINING.tags_path):
            d[p.lower()] = len(os.listdir(os.path.join(settings.TRAINING.tags_path,p)))

        return d
            
    def save_navigation_image(self, tof: dict, cmd_vel: Twist, image, folder: str | None = None) -> bool | str:
        tof_left = tof.get(0, 999)
        tof_right = tof.get(1, 999)
        x = _normalize_velocity(cmd_vel.linear.x)
        y = _normalize_velocity(cmd_vel.linear.y)
        z = _normalize_velocity(cmd_vel.angular.z)
        name = f'nav_{x}_{y}_{z}_{self.filetime("jpg")}'
        save_path = os.path.join(settings.TRAINING.navigation_path, folder) if folder else settings.TRAINING.navigation_path
        os.makedirs(save_path, exist_ok=True)
        return self.save_image(
            image=image,
            path=save_path,
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
            self.get_snapshots(category)
        except Exception:
            return
            

        return True
    
    def category_path(self, category: str) -> str:
        return os.path.join(
            settings.TRAINING.training_images_path,
            category.lower())