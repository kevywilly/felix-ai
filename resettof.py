import board
from digitalio import DigitalInOut
import time
import smbus2

# Use the actual board pin numbers from your pinout
# Pin 32 and Pin 33 (board numbering)

# Let's try to find the correct board constants for pins 32 and 33
pin_tests = [
    # Try different ways board pins might be named
    ("D32", "Pin 32"),
    ("D33", "Pin 33"), 
    ("CEO0", "Pin 32 alt"),  # Sometimes GPIO pins have alternate names
    ("CEO1", "Pin 33 alt"),
]

working_pins = []

for pin_name, description in pin_tests:
    try:
        if hasattr(board, pin_name):
            pin_obj = getattr(board, pin_name)
            test_pin = DigitalInOut(pin_obj)
            test_pin.switch_to_output(value=False)
            working_pins.append((pin_name, pin_obj, description))
            print(f"✅ board.{pin_name} works ({description})")
        else:
            print(f"❌ board.{pin_name} doesn't exist")
    except Exception as e:
        print(f"❌ board.{pin_name} failed: {e}")

print(f"\nWorking pins: {working_pins}")

# Let's also check what board pins are actually available
print("\nAvailable board pins:")
board_attrs = [attr for attr in dir(board) if attr.startswith('D') or attr.startswith('CEO') or attr.startswith('GPIO')]
print(board_attrs[:20])  # Show first 20