from tof.vl53l0x import VL53l0X
import time

if __name__ == "__main__":
    tof = VL53l0X(i2c_bus=7)
    
    while True:
        distance = tof.read_distance()
        print(f"Distance: {distance} mm")
        time.sleep(1)  # Delay 1 second between readings