import smbus2
import time

# I2C address of VL53L0X (default address is 0x29)
VL53L0X_ADDRESS = 0x29
VL53L0X_I2C_SLAVE_DEVICE_ADDRESS = 0x8A

# Registers for VL53L0X (based on its datasheet)
VL53L0X_REG_IDENTIFICATION_MODEL_ID = 0xC0
VL53L0X_REG_SYSTEM_RANGE_START = 0x00
VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR = 0x0B
VL53L0X_REG_RESULT_INTERRUPT_STATUS = 0x13
VL53L0X_REG_RESULT_RANGE_STATUS = 0x14
VL53L0X_REG_RESULT_RANGE_HIGH = 0x1E
VL53L0X_REG_RESULT_RANGE_LOW = 0x1F

class VL53l0X:

    def __init__(self, i2c_bus: int = 7):
        self.i2c_bus = i2c_bus
        self.bus = smbus2.SMBus(7)
        self.address = VL53L0X_ADDRESS
        self.init()

    # Create the I2C bus
    bus = smbus2.SMBus(7)  # Use '1' for I2C-1 bus on most Jetson devices use i2c-7 for jetson orin nano
    bus.open(7)
    def read_byte(self, register):
        return self.bus.read_byte_data(self.address, register)

    def write_byte(self, register, value):
        self.bus.write_byte_data(self.address, register, value)

    def enable_continuous_ranging(self):
        """
        Enable continuous ranging mode.
        """
        self.write_byte(VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG, 0x01)  # Configure the system sequence
        self.write_byte(VL53L0X_REG_SYSRANGE_MODE_CONTINUOUS, 0x02)  # Set to continuous ranging mode

    def init(self):
        try:
            # Perform data initialization as per VL53L0X API
            self.write_byte(0x88, 0x00)
            self.write_byte(0x80, 0x01)
            self.write_byte(0xFF, 0x01)
            self.write_byte(0x00, 0x00)
            self.stop_variable = self.read_byte(0x91)
            self.write_byte(0x00, 0x01)
            self.write_byte(0xFF, 0x00)
            self.write_byte(0x80, 0x00)

            # Recommended Timing Settings
            # Set 2.8V mode
            self.write_byte(0x89, 0x01)  # VL53L0X_REG_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV

            # Set GPIO High Voltage
            self.write_byte(0x84, self.read_byte(0x84) & ~0x10)  # VL53L0X_REG_GPIO_HV_MUX_ACTIVE_HIGH

            # Set Interrupt Polarity to active low
            self.write_byte(0x0C, self.read_byte(0x0C) & ~0x10)

            # Configure the device
            self.write_byte(0x0E, self.read_byte(0x0E) & ~0x10)

            # Set default configuration
            self.write_byte(0x80, 0x01)
            self.write_byte(0xFF, 0x01)
            self.write_byte(0x00, 0x00)
            self.write_byte(0x91, self.stop_variable)
            self.write_byte(0x00, 0x01)
            self.write_byte(0xFF, 0x00)
            self.write_byte(0x80, 0x00)

            # Set measurement timing budget and inter-measurement period
            self.set_measurement_timing_budget(20000)  # 20ms timing budget

            # Perform reference SPAD management
            self.perform_ref_spad_management()

            # Perform static initialization and calibration
            self.perform_ref_calibration()

            # Sensor is now initialized
            return True

        except Exception as e:
            print(f"Initialization error: {e}")
            return False


    def perform_ref_spad_management(self):
        # This is a simplified version. For full implementation, refer to the API.
        count, is_aperture = self.get_spad_info()
        # Perform the SPAD management using the count and is_aperture values
        # ...

    def perform_ref_calibration(self):
    # Perform reference calibration
    # This involves VCSEL period calibration which is essential for accurate measurements
    # Typically, the API does this and the registers are not publicly documented
    # For now, we'll attempt a simplified version
        self.write_byte(0x01, 0x01)  # Start temperature calibration
        time.sleep(0.1)

    def read_distance(self):
        # Start a measurement
        self.write_byte(VL53L0X_REG_SYSTEM_RANGE_START, 0x01)

        # Wait for the measurement to complete
        while True:
            status = self.read_byte(VL53L0X_REG_RESULT_INTERRUPT_STATUS)
            if (status & 0x07) != 0:  # Check if data is ready
                break
            time.sleep(0.005)  # Wait 5ms between checks

        # Read the distance value
        high_byte = self.read_byte(VL53L0X_REG_RESULT_RANGE_HIGH)
        low_byte = self.read_byte(VL53L0X_REG_RESULT_RANGE_LOW)
        distance = (high_byte << 8) | low_byte

        # Clear the interrupt
        self.write_byte(VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR, 0x01)

        # **Check for Invalid Distance Measurements**
        if distance == 8190 or distance == 8191:
            print("Invalid measurement")
            return None  # Or handle accordingly

        return distance
    

    def change_address(self, new_address):
        global vl53l0x_address

        # Validate the new address (must be a 7-bit address, i.e., between 0x08 and 0x77)
        if new_address < 0x08 or new_address > 0x77:
            raise ValueError("Invalid I2C address. Address must be between 0x08 and 0x77.")

        # Write the new I2C address to the sensor
        self.write_byte(VL53L0X_I2C_SLAVE_DEVICE_ADDRESS, new_address)

        # Update the address in the script
        self.address = new_address
        print(f"VL53L0X I2C address changed to 0x{new_address:02X}")

if __name__ == "__main__":
    tof = VL53l0X(i2c_bus=7)
    
    while True:
        distance = tof.read_distance()
        print(f"Distance: {distance} mm")
        time.sleep(1)  # Delay 1 second between readings
