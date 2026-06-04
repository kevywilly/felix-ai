import torch
import cv2
import numpy as np
from torchvision import transforms
import time
from collections import deque

from felix.training.mecanum.model import MecanumSensorFusionNet


class MecanumDriver:
    def __init__(self, model_path, use_fp16=True):
        self.device = torch.device('cuda')
        
        # Load model and config
        print("Loading model...")
        checkpoint = torch.load(model_path)
        
        self.model = MecanumSensorFusionNet().to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        # Load configuration from checkpoint
        config = checkpoint.get('config', {})
        self.tof_max = config.get('tof_max_range', 2000)
        self.max_linear_x = config.get('max_linear_x', 0.5)
        self.max_linear_y = config.get('max_linear_y', 0.3)
        self.max_angular_z = config.get('max_angular_z', 1.0)
        
        print(f"Config loaded - ToF max: {self.tof_max}mm")
        print(f"Velocity limits: x={self.max_linear_x}, y={self.max_linear_y}, z={self.max_angular_z}")
        
        # Convert to FP16
        if use_fp16:
            self.model.half()
        self.use_fp16 = use_fp16
        
        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
        
        # Command smoothing
        self.prev_cmd = np.array([0.0, 0.0, 0.0])
        self.alpha = 0.7
        self.cmd_history = deque(maxlen=3)
        
        # Performance tracking
        self.fps_history = deque(maxlen=30)
        
        # Safety
        self.min_safe_distance = 250  # mm
        self.emergency_stop_distance = 150  # mm
        
        print("Model loaded successfully!")
        
    def predict(self, image, tof_left_mm, tof_right_mm):
        """
        Args:
            image: numpy array (H, W, 3) BGR
            tof_left_mm: left ToF reading in millimeters
            tof_right_mm: right ToF reading in millimeters
            
        Returns:
            dict with linear_x, linear_y, angular_z in m/s and rad/s
        """
        start_time = time.time()
        
        # Preprocess image
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img_tensor = self.transform(image_rgb).unsqueeze(0).to(self.device)
        
        # Preprocess ToF
        tof_tensor = torch.tensor(
            [[tof_left_mm / self.tof_max, tof_right_mm / self.tof_max]], 
            dtype=torch.float32
        ).to(self.device)
        
        # Convert to FP16 if needed
        if self.use_fp16:
            img_tensor = img_tensor.half()
            tof_tensor = tof_tensor.half()
        
        # Inference
        with torch.no_grad():
            output = self.model(img_tensor, tof_tensor)
        
        # Convert to velocities
        cmd_normalized = output.float().cpu().numpy()[0]
        cmd_raw = np.array([
            cmd_normalized[0] * self.max_linear_x,
            cmd_normalized[1] * self.max_linear_y,
            cmd_normalized[2] * self.max_angular_z
        ])
        
        # Smooth commands
        cmd_smooth = self.alpha * cmd_raw + (1 - self.alpha) * self.prev_cmd
        self.prev_cmd = cmd_smooth.copy()
        
        self.cmd_history.append(cmd_smooth.copy())
        if len(self.cmd_history) >= 3:
            cmd_smooth = np.median(np.array(self.cmd_history), axis=0)
        
        # Safety
        cmd_safe = self._apply_safety(cmd_smooth, tof_left_mm, tof_right_mm)
        
        # FPS
        fps = 1.0 / (time.time() - start_time)
        self.fps_history.append(fps)
        
        return {
            'linear_x': float(cmd_safe[0]),
            'linear_y': float(cmd_safe[1]),
            'angular_z': float(cmd_safe[2]),
            'fps': fps,
            'avg_fps': np.mean(self.fps_history)
        }
    
    def _apply_safety(self, cmd, tof_left_mm, tof_right_mm):
        cmd_safe = cmd.copy()
        min_tof = min(tof_left_mm, tof_right_mm)
        
        # Emergency stop
        if min_tof < self.emergency_stop_distance:
            return np.array([0.0, 0.0, 0.0])
        
        # Slow down approaching obstacles
        if min_tof < self.min_safe_distance:
            if cmd_safe[0] > 0:
                scale = (min_tof - self.emergency_stop_distance) / \
                        (self.min_safe_distance - self.emergency_stop_distance)
                cmd_safe[0] *= max(0.0, min(1.0, scale))
        
        # Prevent strafing into obstacles
        if tof_left_mm < self.min_safe_distance and cmd_safe[1] > 0:
            cmd_safe[1] *= 0.3
        if tof_right_mm < self.min_safe_distance and cmd_safe[1] < 0:
            cmd_safe[1] *= 0.3
        
        return cmd_safe


# Example usage
if __name__ == '__main__':
    driver = MecanumDriver('mecanum_resnet50.pth', use_fp16=True)
    
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Get ToF readings (replace with actual sensor reads)
        tof_left = 1000  # mm
        tof_right = 1000  # mm
        
        cmd = driver.predict(frame, tof_left, tof_right)
        
        # Send to robot here
        print(f"Cmd: x={cmd['linear_x']:.3f}, y={cmd['linear_y']:.3f}, "
              f"z={cmd['angular_z']:.3f} | FPS: {cmd['fps']:.1f}")
        
        # Visualize
        cv2.putText(frame, f"FPS: {cmd['avg_fps']:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Navigation', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()