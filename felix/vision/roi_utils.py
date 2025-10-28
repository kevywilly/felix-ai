"""
ROI (Region of Interest) utility functions for consistent image cropping
between training and inference pipelines.
"""

from PIL import Image

def apply_roi_crop(image, roi_height_ratio,  roi_vertical_offset, roi_width_ratio):
    """
    Apply ROI cropping to focus on ground-level obstacles.
    
    Works with both PIL Images (training) and numpy arrays (inference)
    to ensure identical cropping logic between training and deployment.
    
    Args:
        image: PIL Image or numpy array (H, W, C) or (H, W)
        roi_height_ratio: Fraction of image height to keep (0.6 = bottom 60%)
        roi_width_ratio: Fraction of image width to keep (1.0 = full width)
        roi_vertical_offset: Where to start crop (0.4 = start 40% down from top)
        
    Returns:
        Cropped image (same type as input)
    """
    
    if isinstance(image, Image.Image):
        # PIL Image - training pipeline
        width, height = image.size
        
        # Calculate crop boundaries
        crop_height = int(height * roi_height_ratio)
        crop_width = int(width * roi_width_ratio)
        
        # Center the width crop, offset the height crop
        left = (width - crop_width) // 2
        top = int(height * roi_vertical_offset)
        right = left + crop_width
        bottom = top + crop_height
        
        # Ensure we don't exceed image boundaries
        bottom = min(bottom, height)
        right = min(right, width)
        
        # Crop the ROI
        roi_image = image.crop((left, top, right, bottom))
        return roi_image
        
    else:
        # Numpy array - inference pipeline
        if len(image.shape) == 3:
            height, width, _ = image.shape
        else:
            height, width = image.shape
            
        # Calculate crop boundaries (identical logic as PIL)
        crop_height = int(height * roi_height_ratio)
        crop_width = int(width * roi_width_ratio)
        
        # Center the width crop, offset the height crop
        left = (width - crop_width) // 2
        top = int(height * roi_vertical_offset)
        right = left + crop_width
        bottom = top + crop_height
        
        # Ensure we don't exceed image boundaries
        bottom = min(bottom, height)
        right = min(right, width)
        
        # Crop the ROI
        if len(image.shape) == 3:
            roi_image = image[top:bottom, left:right, :]
        else:
            roi_image = image[top:bottom, left:right]
            
        return roi_image


class ROITransform:
    """
    Transform for ROI cropping compatible with torchvision transforms.
    """
    def __init__(self, roi_height_ratio, roi_width_ratio, roi_vertical_offset):
        self.roi_height_ratio = roi_height_ratio
        self.roi_width_ratio = roi_width_ratio
        self.roi_vertical_offset = roi_vertical_offset
        
    def __call__(self, image):
        return apply_roi_crop(
            image, 
            roi_height_ratio=self.roi_height_ratio, 
            roi_width_ratio=self.roi_width_ratio, 
            roi_vertical_offset=self.roi_vertical_offset
        )
