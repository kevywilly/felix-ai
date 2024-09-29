from blinker import signal

# Define a signal
sig_cmd_vel = signal('cmd_vel')
sig_joystick = signal('joystick')
sig_nav_target = signal('nav_target')
sig_raw_image = signal('raw_image')
sig_autodrive = signal('autodrive')
sig_stop=signal('stop')
sig_image_tensor=signal('image_tensor')