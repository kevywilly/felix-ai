class MockRosmaster:
    def __init__(self, car_type, com):
        pass

    def create_receive_threading(self):
        pass

    def get_imu_attitude_data(self):
        return (0, 0, 0)

    def get_magnetometer_data(self):
        return (0, 0, 0)

    def get_gyroscope_data(self):
        return (0, 0, 0)

    def get_accelerometer_data(self):
        return (0, 0, 0)

    def get_motion_data(self):
        return (0, 0, 0)

    def set_motor(self, a, b, c, d):
        pass

    def set_car_motion(self, a, b, c):
        pass