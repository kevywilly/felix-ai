from felix.nodes.autodriver import AutoDriver, Direction
from felix.training.mecanum.inference import MecanumDriver
from lib.interfaces import Twist
from felix.settings import settings
import numpy as np

DEBUG = True


class MecanumAutoDriver(AutoDriver):
    """
    End-to-end learned navigation using sensor fusion (camera + ToF).
    Predicts continuous cmd_vel values directly from visual and ToF inputs.
    """
    
    def __init__(self, **kwargs):
        # Initialize parent with use_nav=True to use nav model path
        super().__init__(model_file=settings.TRAINING.mecanum_model_path, num_targets=3, **kwargs)
        
        # Initialize the mecanum driver
        self.mecanum_driver = None
        if self.model_file_exists:
            try:
                self.mecanum_driver = MecanumDriver(
                    model_path=self.model_file,
                    use_fp16=True
                )
                self.model_loaded = True
                self.logger.info("MecanumDriver initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize MecanumDriver: {e}")
                self.model_loaded = False
        else:
            self.logger.warning(f"Model file not found: {self.model_file}")
            self.model_loaded = False
    
    def predict(self, input) -> Twist:
        """
        Predict cmd_vel using learned model with ToF sensor fusion
        
        Args:
            input: BGR image from camera
            
        Returns:
            Twist command with linear.x, linear.y, angular.z
        """
        if DEBUG:
            print("Making mecanum navigation prediction...")
        
        cmd = Twist()
        
        if not self.is_active:
            return cmd
        
        if not self.model_loaded or self.mecanum_driver is None:
            self.logger.error("MecanumDriver not loaded, cannot make prediction")
            return cmd
        
        # Get ToF sensor readings (in mm)
        tof_left = self.tof.get(0, 1200)  # Default to max range if not available
        tof_right = self.tof.get(1, 1200)
        
        try:
            # Get prediction from model
            prediction = self.mecanum_driver.predict(
                image=input,
                tof_left_mm=tof_left,
                tof_right_mm=tof_right
            )
            
            # Extract velocities
            cmd.linear.x = prediction['linear_x']
            cmd.linear.y = prediction['linear_y']
            cmd.angular.z = prediction['angular_z']
            
            # Log prediction info
            self.logger.info(
                f"MecanumNav - x: {cmd.linear.x:.3f}, y: {cmd.linear.y:.3f}, "
                f"z: {cmd.angular.z:.3f} | ToF L:{tof_left}mm R:{tof_right}mm | "
                f"FPS: {prediction['avg_fps']:.1f}"
            )
            
            if DEBUG:
                print(f"Prediction: x={cmd.linear.x:.3f}, y={cmd.linear.y:.3f}, "
                      f"z={cmd.angular.z:.3f}, fps={prediction['fps']:.1f}")
            
        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            # Return stop command on error
            cmd = Twist()
        
        return cmd
    
    def load_state_dict(self, model):
        """
        Override parent's load_state_dict since we use MecanumDriver
        which handles model loading internally
        """
        # Model loading is handled in __init__ via MecanumDriver
        pass
    
    def _create_model(self):
        """
        Override parent's _create_model since we use MecanumDriver
        which handles model creation internally
        """
        # Model creation is handled in __init__ via MecanumDriver
        return None


class MecanumAutoDriverWithToFFallback(MecanumAutoDriver):
    """
    Enhanced version with ToF-based safety fallback.
    If model predicts unsafe actions, override with ToF-based logic.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tof_threshold = 200  # mm - threshold for ToF override
        self.use_tof_override = True  # Enable/disable ToF override
    
    def predict(self, input) -> Twist:
        """
        Predict with additional ToF-based safety override
        """
        # Get base prediction from model
        cmd = super().predict(input)
        
        if not self.use_tof_override:
            return cmd
        
        # Get ToF readings
        tof_left = self.tof.get(0, 1200)
        tof_right = self.tof.get(1, 1200)
        min_tof = min(tof_left, tof_right)
        
        # ToF-based safety overrides
        if min_tof < self.tof_threshold:
            self.logger.warning(
                f"ToF override activated! min_tof={min_tof}mm < {self.tof_threshold}mm"
            )
            
            # Emergency stop if very close
            if min_tof < 150:
                self.logger.warning("Emergency stop - obstacle too close!")
                return Twist()  # Full stop
            
            # Slow down forward motion
            if cmd.linear.x > 0:
                scale = (min_tof - 150) / (self.tof_threshold - 150)
                cmd.linear.x *= max(0.0, min(1.0, scale))
                self.logger.info(f"Reduced forward speed by {(1-scale)*100:.0f}%")
            
            # Reduce strafe toward obstacle
            if tof_left < self.tof_threshold and cmd.linear.y > 0:
                cmd.linear.y *= 0.3
                self.logger.info("Reduced strafe left due to left obstacle")
            
            if tof_right < self.tof_threshold and cmd.linear.y < 0:
                cmd.linear.y *= 0.3
                self.logger.info("Reduced strafe right due to right obstacle")
        
        return cmd