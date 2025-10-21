#!/usr/bin/env python3
import logging
import serial
import json
import asyncio
import time
from felix.signals import Topics
from lib.interfaces import SensorReading
from lib.nodes.base import BaseNode


class PicoSensors(BaseNode):
    def __init__(self, **kwargs):

        super(PicoSensors, self).__init__(**kwargs)

        self.logger.info("Initializing Pico sensors")
        self.readings = {} 
        self.ser = serial.Serial(
            port='/dev/mypico',
            baudrate=115200,  # Adjust if your Pico uses different baud rate
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0.1,  # Reduced timeout for faster response
            write_timeout=0.1
        )
        # Flush any existing data in buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.logger.info("Pico sensor initialized")

    @staticmethod
    def is_pico_connected():
        """Check if Raspberry Pi Pico is connected via USB"""
        try:
            import subprocess
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            return '239a:80f4' in result.stdout or 'Raspberry Pi Pico' in result.stdout
        except:
            return False

    def read_data(self):
        # Read all available data at once to reduce latency
        while self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    data = json.loads(line)
                    reading = SensorReading.from_json(data)
                    Topics.pico_sensors.send(payload=reading)
                    self.logger.debug(reading)
                    #if reading.value < 250:
                    #    print(reading)
            except json.JSONDecodeError as e:
                #print(line)
                self.logger.error(f"JSON decode error: {e}")
            except UnicodeDecodeError as e:
                self.logger.error(f"Unicode decode error: {e}")
           

    def spinner(self):
        self.read_data()

    def shutdown(self):
        if self.ser.is_open:
            self.ser.close()
            self.logger.info("Serial connection closed")

if __name__ == "__main__":
    node = PicoSensors()
    asyncio.run(node.spin())
        