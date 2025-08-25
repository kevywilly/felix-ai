#!/usr/bin/env python3
from felix.vision.tof import TOFArray


if __name__ == "__main__":
    array = TOFArray()
    while True:
        print(array.get_readings())
