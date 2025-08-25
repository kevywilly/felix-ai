"""
ROI (Region of Interest) utility functions for consistent image cropping
between training and inference pipelines.
"""

import numpy as np
from PIL import Image


def apply_roi_crop(image, roi_height_ratio=0.6, roi_width_ratio=1.0, roi_vertical_offset=0.4):
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
    def __init__(self, roi_height_ratio=0.6, roi_width_ratio=1.0, roi_vertical_offset=0.4):
        self.roi_height_ratio = roi_height_ratio
        self.roi_width_ratio = roi_width_ratio
        self.roi_vertical_offset = roi_vertical_offset
        
    def __call__(self, image):
        return apply_roi_crop(
            image, 
            self.roi_height_ratio, 
            self.roi_width_ratio, 
            self.roi_vertical_offset
        )


# Predefined ROI configurations for common use cases
ROI_CONFIGS = {
    'ground_robot': {
        'roi_height_ratio': 0.6,
        'roi_width_ratio': 1.0,
        'roi_vertical_offset': 0.4
    },
    'indoor_furniture': {
        'roi_height_ratio': 0.65,
        'roi_width_ratio': 1.0,
        'roi_vertical_offset': 0.35
    },
    'outdoor_ground': {
        'roi_height_ratio': 0.7,
        'roi_width_ratio': 1.0,
        'roi_vertical_offset': 0.3
    },
    'horizon_focus': {
        'roi_height_ratio': 0.6,
        'roi_width_ratio': 1.0,
        'roi_vertical_offset': 0.2
    }
}


def get_roi_config(config_name='ground_robot'):
    """
    Get predefined ROI configuration.
    
    Args:
        config_name: One of 'ground_robot', 'indoor_furniture', 'outdoor_ground', 'horizon_focus'
        
    Returns:
        Dictionary with ROI parameters
    """
    return ROI_CONFIGS.get(config_name, ROI_CONFIGS['ground_robot'])


# Example usage and testing
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    
    def test_roi_consistency():
        """Test that PIL and numpy processing give identical results"""
        # Create a test image
        test_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        test_pil = Image.fromarray(test_array)
        
        # Apply ROI to both
        roi_array = apply_roi_crop(test_array)
        roi_pil = apply_roi_crop(test_pil)
        roi_pil_array = np.array(roi_pil)
        
        # Check if results are identical
        if np.array_equal(roi_array, roi_pil_array):
            print("✓ ROI processing is consistent between PIL and numpy")
        else:
            print("✗ ROI processing differs between PIL and numpy")
            print(f"Array shape: {roi_array.shape}")
            print(f"PIL->Array shape: {roi_pil_array.shape}")
    
    test_roi_consistency()
    
    # Test different configurations
    for config_name, config in ROI_CONFIGS.items():
        print(f"{config_name}: {config}")