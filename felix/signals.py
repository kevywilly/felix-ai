from blinker import signal

# Define a signal
cmd_vel_signal = signal('cmd_vel_signal')
joystick_signal = signal('joystic_signal')
twist_signal = signal('twist_signal')
nav_target_signal = signal('nav_target_signal')
raw_image_signal = signal('image_signal')
autodrive_signal = signal('autodrive_signal')