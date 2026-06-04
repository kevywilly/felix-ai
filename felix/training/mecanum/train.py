import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import cv2
from torchvision import transforms
from pathlib import Path
from torch.amp import autocast
from torch.cuda.amp import GradScaler
from felix.settings import settings
from felix.training.mecanum.model import MecanumSensorFusionNet

def _denormalize_velocity(value: int, scale: int = 1000) -> float:
    return float(value) / scale


class MecanumDataset(Dataset):
    def __init__(self, data_dir=settings.TRAINING.navigation_path, transform=None, tof_max_range=1200): #2000
        """
        Args:
            data_dir: Directory containing nav_*.jpg images
            transform: Image transforms
            tof_max_range: Maximum ToF sensor range in mm (e.g., 2000mm = 2m)
        """
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.tof_max = tof_max_range
        
        # Find all nav images
        self.image_files = sorted(self.data_dir.rglob("nav_*.jpg"))
        print(f"Found {len(self.image_files)} training images")
        
        # Parse filenames to get labels
        self.samples = []
        for img_path in self.image_files:
            parsed = self._parse_filename(img_path.name)
            if parsed is not None:
                self.samples.append({
                    'image_path': img_path,
                    'prev_tof_left': parsed['prev_tof_left'],
                    'prev_tof_right': parsed['prev_tof_right'],
                    'prev_linear_x': parsed['prev_linear_x'],
                    'prev_linear_y': parsed['prev_linear_y'],
                    'prev_angular_z': parsed['prev_angular_z'],
                    'tof_left': parsed['tof_left'],
                    'tof_right': parsed['tof_right'],
                    'linear_x': parsed['linear_x'],
                    'linear_y': parsed['linear_y'],
                    'angular_z': parsed['angular_z']
                })
        
        print(f"Successfully parsed {len(self.samples)} samples")
        
    def _parse_filename(self, filename):
        """
        Parse filename: nav_prevL_prevR_prevX_prevY_prevZ_curL_curR_curX_curY_curZ_timestamp.jpg
        """
        try:
            # Remove 'nav_' prefix and '.jpg' suffix
            parts = filename.replace('nav_', '').replace('.jpg', '').split('_')
            
            if len(parts) < 11:
                return None
            
            return {
                'prev_tof_left': int(parts[0]),
                'prev_tof_right': int(parts[1]),
                'prev_linear_x': _denormalize_velocity(int(parts[2])),
                'prev_linear_y': _denormalize_velocity(int(parts[3])),
                'prev_angular_z': _denormalize_velocity(int(parts[4])),
                'tof_left': int(parts[5]),
                'tof_right': int(parts[6]),
                'linear_x': _denormalize_velocity(int(parts[7])),
                'linear_y': _denormalize_velocity(int(parts[8])),
                'angular_z': _denormalize_velocity(int(parts[9])),
                # parts[10] is timestamp, ignore for now
            }
        except (ValueError, IndexError) as e:
            print(f"Failed to parse {filename}: {e}")
            return None
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        
        # Load image
        image = cv2.imread(str(sample['image_path']))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        if self.transform:
            image = self.transform(image)
        
        # Current ToF sensors - normalize to [0, 1]
        tof = torch.tensor([
            sample['tof_left'] / self.tof_max,
            sample['tof_right'] / self.tof_max
        ], dtype=torch.float32)
        
        # Target command velocities - normalize to [-1, 1]
        # Adjust these max values based on your robot's capabilities
        max_linear_x = settings.VEHICLE.max_linear_velocity #0.5
        max_linear_y = settings.VEHICLE.max_linear_velocity #0.3
        max_angular_z = settings.VEHICLE.max_angular_velocity #1.0
        
        cmd = torch.tensor([
            sample['linear_x'] / max_linear_x,
            sample['linear_y'] / max_linear_y,
            sample['angular_z'] / max_angular_z
        ], dtype=torch.float32)
        
        # Clamp to [-1, 1]
        cmd = torch.clamp(cmd, -1.0, 1.0)
        
        return image, tof, cmd


def train_model(data_dir, 
                epochs=100, 
                batch_size=32, 
                learning_rate=0.001,
                val_split=0.2,
                tof_max_range=2000,
                max_linear_x=0.5,
                max_linear_y=0.3,
                max_angular_z=1.0,
                use_amp=True,
                save_path='mecanum_resnet50.pth'):
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Training on: {device}")
    print(f"Velocity limits: linear_x={max_linear_x}, linear_y={max_linear_y}, angular_z={max_angular_z}")
    
    # Data augmentation for training
    train_transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    # Create dataset
    print("\nLoading dataset...")
    full_dataset = MecanumDataset(data_dir, train_transform, tof_max_range)
    
    if len(full_dataset) == 0:
        raise ValueError("No valid samples found in dataset!")
    
    # Train/val split
    val_size = int(val_split * len(full_dataset))
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )
    
    # Update validation transform
    val_dataset.dataset.transform = val_transform
    
    print(f"Training samples: {train_size}")
    print(f"Validation samples: {val_size}")
    
    # Data loaders
    train_loader = DataLoader(
        train_dataset, 
        batch_size=batch_size, 
        shuffle=True,
        num_workers=2,
        pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, 
        batch_size=batch_size,
        num_workers=2,
        pin_memory=True
    )
    
    # Model
    model = MecanumSensorFusionNet().to(device)
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Loss and optimizer
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5, verbose=False  # Changed verbose=False
    )
    
    # Mixed precision training - FIXED
    scaler = GradScaler() if use_amp else None
    
    # Training loop
    best_val_loss = float('inf')
    
    print("\nStarting training...")
    print("-" * 80)
    
    for epoch in range(epochs):
        # Training phase
        model.train()
        train_loss = 0
        
        for batch_idx, (images, tof, commands) in enumerate(train_loader):
            images = images.to(device, non_blocking=True)
            tof = tof.to(device, non_blocking=True)
            commands = commands.to(device, non_blocking=True)
            
            optimizer.zero_grad()
            
            if use_amp:
                with autocast(device_type='cuda', dtype=torch.float16):
                    outputs = model(images, tof)
                    loss = criterion(outputs, commands)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                outputs = model(images, tof)
                loss = criterion(outputs, commands)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
            
            train_loss += loss.item()
        
        avg_train_loss = train_loss / len(train_loader)
        
        # Validation phase
        model.eval()
        val_loss = 0
        
        with torch.no_grad():
            for images, tof, commands in val_loader:
                images = images.to(device, non_blocking=True)
                tof = tof.to(device, non_blocking=True)
                commands = commands.to(device, non_blocking=True)
                
                if use_amp:
                    with autocast(device_type='cuda', dtype=torch.float16):  # FIXED
                        outputs = model(images, tof)
                        loss = criterion(outputs, commands)
                else:
                    outputs = model(images, tof)
                    loss = criterion(outputs, commands)
                
                val_loss += loss.item()
        
        avg_val_loss = val_loss / len(val_loader)
        
        # Update learning rate
        scheduler.step(avg_val_loss)
        
        # Print progress
        print(f"Epoch {epoch+1:3d}/{epochs} | "
              f"Train: {avg_train_loss:.6f} | "
              f"Val: {avg_val_loss:.6f} | "
              f"LR: {optimizer.param_groups[0]['lr']:.6f}")
        
        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss': avg_train_loss,
                'val_loss': avg_val_loss,
                'config': {
                    'tof_max_range': tof_max_range,
                    'max_linear_x': max_linear_x,
                    'max_linear_y': max_linear_y,
                    'max_angular_z': max_angular_z
                }
            }, save_path)
            print(f"        ✓ Best model saved (val_loss: {best_val_loss:.6f})")
    
    print("-" * 80)
    print(f"Training complete! Best validation loss: {best_val_loss:.6f}")
    print(f"Model saved to: {save_path}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Train Mecanum navigation model')
    parser.add_argument('--data_dir', type=str, default=settings.TRAINING.navigation_path,
                       help='Directory containing nav_*.jpg images')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--tof_max', type=int, default=2000,
                       help='Maximum ToF range in mm')
    parser.add_argument('--max_linear_x', type=float, default=0.5)
    parser.add_argument('--max_linear_y', type=float, default=0.3)
    parser.add_argument('--max_angular_z', type=float, default=1.0)
    parser.add_argument('--output', type=str, default=settings.TRAINING.mecanum_model_path)
    parser.add_argument('--no_amp', action='store_true',
                       help='Disable automatic mixed precision')
    
    args = parser.parse_args()

    
    train_model(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        tof_max_range=args.tof_max,
        max_linear_x=args.max_linear_x,
        max_linear_y=args.max_linear_y,
        max_angular_z=args.max_angular_z,
        use_amp=not args.no_amp,
        save_path=args.output
    )


"""
MSE Loss Interpretation for Mecanum Navigation Model

This is a REGRESSION task (continuous velocity prediction), not classification.
Cannot directly compare to classification accuracy (0.98 = 98% correct).

MSE Loss Quality Guide:
┌───────────┬───────┬─────────────────────────┬─────────────────┐
│ MSE Loss  │ RMSE  │ Real Error (0.5 m/s max)│ Quality         │
├───────────┼───────┼─────────────────────────┼─────────────────┤
│ 0.250     │ 0.50  │ ±0.25 m/s               │ Poor - unusable │
│ 0.100     │ 0.32  │ ±0.16 m/s               │ Mediocre        │
│ 0.050     │ 0.22  │ ±0.11 m/s               │ Decent          │
│ 0.017     │ 0.13  │ ±0.065 m/s              │ Good ✅         │
│ 0.010     │ 0.10  │ ±0.05 m/s               │ Very good       │
│ 0.001     │ 0.03  │ ±0.015 m/s              │ Excellent       │
└───────────┴───────┴─────────────────────────┴─────────────────┘

Conversion to "Accuracy-like" metric:
    RMSE = sqrt(MSE)
    Error per dimension = sqrt(MSE / 3)  # 3 outputs: linear.x, linear.y, angular.z
    Pseudo-accuracy = 1 - error_per_dimension
    
    Example: MSE=0.017 → ~92.5% "accuracy"

Better metric: R² Score (Coefficient of Determination)
    1.0  = Perfect predictions
    >0.9 = Excellent (90% of variance explained)
    >0.8 = Good
    >0.7 = Acceptable
    <0.5 = Poor

Real-world interpretation:
    If max_linear_x = 0.5 m/s and MSE = 0.017:
    - When commanding 0.3 m/s, model predicts 0.235 to 0.365 m/s
    - Average error: ±6.5 cm/s
    - This is typically good enough for indoor navigation
"""