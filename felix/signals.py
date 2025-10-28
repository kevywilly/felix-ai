from blinker import signal

class Topics:
    cmd_vel = signal('cmd_vel')
    joystick = signal('joystick')
    nav_target = signal('nav_target')
    raw_image = signal('raw_image')
    autodrive = signal('autodrive')
    stop = signal('stop')
    image_tensor = signal('image_tensor')
    tof = signal('tof')
    ir = signal('ir')
    prediction = signal('prediction')
    pico_sensors = signal('pico_sensors')
    nav_capture = signal('nav_capture')