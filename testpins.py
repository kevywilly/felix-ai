import Jetson.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

GPIO.setup([12,13], GPIO.OUT, initial=GPIO.HIGH)

print(GPIO.input(12))  # Check if GPIO07 is HIGH
print(GPIO.input(13))  # Check if GPIO13 is HIGH

GPIO.output(12, GPIO.LOW)  # Set GPIO12 to LOW
GPIO.output(13, GPIO.LOW)  # Set GPIO13 to LOW

print(GPIO.input(12))  # Check if GPIO07 is LOW
print(GPIO.input(13))  # Check if GPIO13 is LOW

GPIO.cleanup()