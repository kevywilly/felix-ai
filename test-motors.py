from src.motion.rosmaster import Rosmaster
import time

bot = Rosmaster(car_type=2, com="/dev/myserial")
bot.create_receive_threading()
bot.set_motor(50,50,50,50)
time.sleep(2)
bot.set_motor(0,0,0,0)
