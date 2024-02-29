from rplidar import RPLidar
import numpy as np

lidar = RPLidar('/dev/rplidar')

info = lidar.get_info()
print(info)

health = lidar.get_health()
print(health)
import logging
logger = logging.getLogger(__name__)
for i, scan in enumerate(lidar.iter_scans()):

    print('%d: Got %d measurments' % (i, len(scan)))
    print(f'\nITERATION: {i}')
    print("========================")
    ar = np.array(scan).astype(int)
    #for item in scan:
    #    data = 
    #    print(f'confidence: {item[0]}, angle: {int(item[1])}, dist: {int(item[2])}')
    ar2 = np.zeros((360,1))
    
    for measure in ar:
        ar2[measure[1]] = [measure[2]]
        ar3 = ar2.reshape(1,360).astype(int)
    
    logger.error(ar3)

    if i > 10:
        break

lidar.stop()
lidar.stop_motor()
lidar.disconnect()