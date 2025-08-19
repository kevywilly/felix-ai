import time
from lib.controllers.rosmaster import Rosmaster
bot = Rosmaster(car_type=2, com="/dev/myserial")
bot.create_receive_threading()
data = bot.get_imu_attitude_data()
print(data)
bot.set_motor(50,50,50,50)
time.sleep(2)
bot.set_motor(0,0,0,0)