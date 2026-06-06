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
    detections = signal('detections')
    lidar = signal("lidar")
    # Toggles the RPLidar's spin motor (and its reader) on/off from the UI.
    # Like `seek`/`autodrive`, travels as a signal so it reaches the spun
    # LidarSensor and not the non-spun UI-side copy. payload=bool (True=on).
    lidar_motor = signal('lidar_motor')
    # Seek control travels as signals (not direct method calls) so it reaches the
    # spun ObjectSeeker even though the module is instantiated twice -- mirrors how
    # `autodrive` is toggled. See test/test_object_seeker_signal.py.
    seek = signal('seek')
    seek_target = signal('seek_target')