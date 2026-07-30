#!/usr/bin/env python

# Program to turn off the transmitter completely to save power at the end of the mission, if that matters to you
# just running  sudo systemctl stop wenet_tx.service   leaves the transmitter on at full power
# This could be added to the root cron, eg.  @reboot sleep 10800 && /home/pi/wenet/tx/sleep_lora.py

import spidev
import RPi.GPIO as GPIO

def sleep_lora():
    # 1. Open SPI Bus 0, Device 0 (CE0)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1000000

    # 2. Write to RegOpMode (Address 0x01)
    # To WRITE via SPI on this chip, we set the Most Significant Bit of the address to 1.
    # 0x01 becomes 0x81.
    # We send 0x00 as the data, which puts the module in FSK/OOK Sleep mode and disables the high-frequency oscillator.
    try:
        spi.xfer2([0x81, 0x00])
        print("LoRa module commanded to Sleep Mode.")
    finally:
        spi.close()

    # 3. Prevent Parasitic Power Draw
    # If Pi pins are left HIGH, they can leak current into the LoRa module's logic pins.
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    
    # Your specific pinout: CE0(8), DIO0(25), DIO5(24), DIO2/PCM(21), MOSI(10), MISO(9), SCK(11)
    lora_pins = [8, 25, 24, 21, 10, 9, 11]
    
    # Set all to INPUT with a pull-down resistor to ground them
    GPIO.setup(lora_pins, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    print("GPIO pins grounded to prevent leakage.")

if __name__ == "__main__":
    sleep_lora()
