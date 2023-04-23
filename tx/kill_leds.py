#!/usr/bin/env python3
#
#   PCA9685 LED Killer
#
#   Shutdown all LEDs on a particular daughterboard in use in some Wenet Payloads
#   that has 3x LEDs that are always powered up on boot...
#   ... maybe we should do something with these LEDs instead of just shutting them down? I dunno.
#
#   LEDs are attached to PCA9685 LED pins 0-8
#
#   Dependencies:
#   sudo pip3 install adafruit-circuitpython-pca9685
#   Then enable I2C in raspi-config
#
#   Add to /etc/rc.local to run on boot.
#   python3 /home/pi/wenet/tx/kill_leds.py

from board import SCL, SDA
import busio

# Import the PCA9685 module.
from adafruit_pca9685 import PCA9685

ADDRESS = 0x55
LED_NUMBERS = [0,1,2,3,4,5,6,7,8]
LED_SETTING = 0xFFFF

# Create the I2C bus interface.
i2c_bus = busio.I2C(SCL, SDA)

# Create a simple PCA9685 class instance.
pca = PCA9685(i2c_bus,address=ADDRESS)

# Set the PWM frequency to 60hz.
pca.frequency = 60

# LEDs are low-side switched, to set to 0xFFFF to turn off completely.
for _led in LED_NUMBERS:
    pca.channels[_led].duty_cycle = LED_SETTING

print("LEDs disabled.")