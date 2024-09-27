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

    #print(ar)

    if i > 10:
        break

lidar.stop()
lidar.stop_motor()
lidar.disconnect()