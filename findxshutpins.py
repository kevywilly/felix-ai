#!/usr/bin/env python3
"""
Script to find the correct XSHUT pins for VL53L0X sensors
by systematically testing all available GPIO pins
"""

import board
from digitalio import DigitalInOut
import time
import smbus2

class SimpleI2C:
    def __init__(self, bus_num=7):
        self.bus = smbus2.SMBus(bus_num)
    
    def scan(self):
        """Scan for I2C devices"""
        devices = []
        for addr in range(0x08, 0x78):
            try:
                self.bus.read_byte(addr)
                devices.append(addr)
            except:
                pass
        return devices
    
    def close(self):
        self.bus.close()

def test_pin_effect(pin_name, pin_obj, i2c):
    """Test if a GPIO pin affects VL53L0X sensor visibility"""
    try:
        # Initialize pin as output
        gpio_pin = DigitalInOut(pin_obj)
        gpio_pin.switch_to_output(value=True)  # Start HIGH
        
        print(f"\nTesting {pin_name}:")
        
        # Scan with pin HIGH
        time.sleep(0.2)
        devices_high = i2c.scan()
        print(f"  Pin HIGH: {[hex(addr) for addr in devices_high]}")
        
        # Set pin LOW
        gpio_pin.value = False
        time.sleep(0.2)
        devices_low = i2c.scan()
        print(f"  Pin LOW:  {[hex(addr) for addr in devices_low]}")
        
        # Set pin HIGH again
        gpio_pin.value = True
        time.sleep(0.2)
        devices_high_again = i2c.scan()
        print(f"  Pin HIGH again: {[hex(addr) for addr in devices_high_again]}")
        
        # Check if pin affects sensor visibility
        high_count = len(devices_high)
        low_count = len(devices_low)
        
        if high_count != low_count:
            print(f"  🎯 POTENTIAL XSHUT PIN! Changes device count: {high_count} -> {low_count}")
            return True
        elif devices_high != devices_low:
            print(f"  🎯 POTENTIAL XSHUT PIN! Changes device addresses")
            return True
        else:
            print(f"  ❌ No effect on sensors")
            return False
            
    except Exception as e:
        print(f"  ⚠️  Error testing {pin_name}: {e}")
        return False
    finally:
        try:
            # Cleanup - set pin back to HIGH and release
            gpio_pin.value = True
            gpio_pin.deinit()
        except:
            pass

def main():
    print("🔍 VL53L0X XSHUT Pin Finder")
    print("=" * 50)
    
    i2c = SimpleI2C(7)
    
    # Initial scan
    print("Initial I2C scan:")
    initial_devices = i2c.scan()
    print(f"Found devices: {[hex(addr) for addr in initial_devices]}")
    
    if not initial_devices:
        print("❌ No VL53L0X sensors found! Check connections.")
        return
    
    print(f"\n✅ Found {len(initial_devices)} sensor(s)")
    print("Now testing each GPIO pin to see which ones control the sensors...\n")
    
    # Get all available board pins
    available_pins = []
    pin_names = ['D4', 'D5', 'D6', 'D7', 'D10', 'D11', 'D12', 'D13', 'D16', 'D17', 
                 'D18', 'D19', 'D20', 'D21', 'D22', 'D23', 'D24', 'D25', 'D26', 'D27']
    
    for pin_name in pin_names:
        if hasattr(board, pin_name):
            pin_obj = getattr(board, pin_name)
            available_pins.append((pin_name, pin_obj))
    
    print(f"Testing {len(available_pins)} available GPIO pins...\n")
    
    # Test each pin
    potential_xshut_pins = []
    
    for pin_name, pin_obj in available_pins:
        if test_pin_effect(pin_name, pin_obj, i2c):
            potential_xshut_pins.append(pin_name)
        time.sleep(0.1)  # Small delay between tests
    
    # Results
    print("\n" + "=" * 50)
    print("🎯 RESULTS:")
    
    if potential_xshut_pins:
        print(f"✅ Found {len(potential_xshut_pins)} potential XSHUT pins:")
        for pin in potential_xshut_pins:
            print(f"  - board.{pin}")
            
        print(f"\n💡 Update your code to use these pins:")
        print("xshut = [")
        for i, pin in enumerate(potential_xshut_pins[:2]):  # Only show first 2
            print(f"    DigitalInOut(board.{pin}),  # Sensor {i}")
        print("]")
        
        # Test combination if we found 2+ pins
        if len(potential_xshut_pins) >= 2:
            print(f"\n🧪 Testing combination of {potential_xshut_pins[0]} and {potential_xshut_pins[1]}:")
            test_pin_combination(potential_xshut_pins[:2], i2c)
            
    else:
        print("❌ No XSHUT pins found!")
        print("This could mean:")
        print("  1. XSHUT pins are not connected")
        print("  2. XSHUT pins are tied to VCC (always on)")
        print("  3. XSHUT pins are connected to different GPIO pins not tested")
        print("  4. Sensors don't support XSHUT control")
    
    i2c.close()

def test_pin_combination(pin_names, i2c):
    """Test a combination of two pins to see if they can control 2 sensors independently"""
    try:
        pins = []
        for pin_name in pin_names:
            pin_obj = getattr(board, pin_name)
            gpio_pin = DigitalInOut(pin_obj)
            gpio_pin.switch_to_output(value=True)
            pins.append(gpio_pin)
        
        print(f"  Both pins HIGH:")
        time.sleep(0.2)
        devices = i2c.scan()
        print(f"    Devices: {[hex(addr) for addr in devices]}")
        
        print(f"  {pin_names[0]} LOW, {pin_names[1]} HIGH:")
        pins[0].value = False
        pins[1].value = True
        time.sleep(0.2)
        devices = i2c.scan()
        print(f"    Devices: {[hex(addr) for addr in devices]}")
        
        print(f"  {pin_names[0]} HIGH, {pin_names[1]} LOW:")
        pins[0].value = True
        pins[1].value = False
        time.sleep(0.2)
        devices = i2c.scan()
        print(f"    Devices: {[hex(addr) for addr in devices]}")
        
        print(f"  Both pins LOW:")
        pins[0].value = False
        pins[1].value = False
        time.sleep(0.2)
        devices = i2c.scan()
        print(f"    Devices: {[hex(addr) for addr in devices]}")
        
        # Cleanup
        for pin in pins:
            pin.value = True
            pin.deinit()
            
    except Exception as e:
        print(f"    Error testing combination: {e}")

if __name__ == "__main__":
    main()
    print("\nExiting...")