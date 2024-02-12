#!/usr/bin/env python3
import atexit
from src.motion.rosmaster import Rosmaster
import numpy as np
import pandas as pd
import time
bot = Rosmaster(car_type=2, com="/dev/myserial")
bot.create_receive_threading()

results = []

ticks_per_revolution = 56*11*4 # ratio * magnetic loops * poles*2
gear_ratio = 56

def test_vel(x,y,z):
    bot.set_car_motion(x,y,z)
    time.sleep(3)
    x_, y_, z_ =  bot.get_motion_data()

    result = (x, y, z, x_, y_, z_)
    print(result)
    return result



def vel_test():
    print('--- running vel test---')
    ar = []
    for i in range (0, 5):
        ar.append(
            test_vel(i/10.0,0,0) 
        )
        ar.append(
            test_vel(0, i/10.0,0) 
        )
        ar.append(
            test_vel(0,0,i/10.0) 
        )
        ar.append(
            test_vel(0,0,2*i/10.0) 
        )
        ar.append(
            test_vel(0,0,3*i/10.0) 
        )
        

    bot.set_car_motion(0,0,0)
    print('-----vel test----')
    results = np.array(ar)
    df = pd.DataFrame(results)
    df.columns = ['x','y','z','vx','vy','omega']
    df.to_csv('vel_test.csv')
    print(results)

def test_pow(p):
    bot.set_motor(p,p,p,p)
    time.sleep(1)
    x_, y_, z_ =  bot.get_motion_data()

    result = (p/100.0, x_, y_, z_)
    print(result)
    return result

def pow_test():
    print('--- running power test---')
    ar = []
    for i in range (0,100,10):
        ar.append(test_pow(i))


    bot.set_car_motion(0,0,0)

    print('-----power test----')
    results = np.array(ar)
    df = pd.DataFrame(results)
    df.columns = ['power','vx','vy','omega']
    df.to_csv('power_test.csv')
    print(results)
       

def rpm_test():
    ar = np.zeros(5)
    for i in range (1,11):
        p = i*10
        bot.set_motor(p,p,p,p)
        time.sleep(2)
        t0 = time.time()
        ticks0 = np.array(bot.get_motor_encoder())
        time.sleep(2)
        t1 = time.time()
        ticks1 = np.array(bot.get_motor_encoder())
        tick_count = ticks1-ticks0
        time_diff = t1-t0
        rpm = 60*(tick_count/time_diff)/ticks_per_revolution
        print(p,rpm)
        
        ar = np.append(ar,[p])
        ar = np.append(ar,rpm)
        print(ar)
        
    ar = ar.reshape(-1,5)
    df = pd.DataFrame(ar)
    df.columns = ['power','rpm0','rpm1','rpm2', 'rpm3']
    df.to_csv('rpm_test.csv')
    print(df)


        
def stop():
    bot.set_motor(0,0,0,0)


if __name__ == "__main__":
    #pow_test()
    #time.sleep(2)
    #vel_test()
    atexit.register(stop)
    stop()
    rpm_test()
    stop()
    