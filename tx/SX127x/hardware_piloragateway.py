""" Defines the BOARD class that contains the board pin mappings. """

# Copyright 2015 Mark Jessop <vk5qi@rfhead.net>
#
# This file is part of pySX127x.
#
# pySX127x is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public
# License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# pySX127x is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You can be released from the requirements of the license by obtaining a commercial license. Such a license is
# mandatory as soon as you develop commercial activities involving pySX127x without disclosing the source code of your
# own applications, or shipping pySX127x with a closed source product.
#
# You should have received a copy of the GNU General Public License along with pySX127x.  If not, see
# <http://www.gnu.org/licenses/>.


import RPi.GPIO as GPIO
import spidev
import time


class HardwareInterface(object):
    """ Board initialisation/teardown and pin configuration is kept here.
        This is the HabSupplies PiLoraGateway v2.4 Shield.
        Schematic for this board is here: https://github.com/PiInTheSky/pits-hardware/blob/master/PiLoraGatewayV2.4.pdf
        Only the DIO0 and DIO5 pins are wired up
    """
    # Note that the BCOM numbering for the GPIOs is used.

    # The spi object is kept here
    spi_device = 0
    spi = None
    spi_speed = 1000000

    def __init__(self, device=0):
        """ Configure the Raspberry GPIOs
        :rtype : None
        """
        self.spi_device = device
        GPIO.setmode(GPIO.BCM)
        
        if device == 0:
            self.LED = 5
            self.DIO0 = 25
            self.DIO5 = 24
        else:
            self.LED = 21
            self.DIO0 = 16
            self.DIO5 = 12

        GPIO.setup(self.LED, GPIO.OUT)
        GPIO.output(self.LED, 0)
        # DIOx
        for gpio_pin in [self.DIO0, self.DIO5]:
            GPIO.setup(gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        # blink 2 times to signal the board is set up
        self.blink(.1, 2)

    def teardown(self):
        """ Cleanup GPIO and SpiDev """
        GPIO.cleanup()
        self.spi.close()

    def SpiDev(self):
        """ Init and return the SpiDev object
        :return: SpiDev object
        :rtype: SpiDev
        """
        self.spi = spidev.SpiDev()
        self.spi.open(0, self.spi_device)
        self.spi.max_speed_hz = self.spi_speed
        return self.spi

    def add_event_detect(self,dio_number, callback):
        """ Wraps around the GPIO.add_event_detect function
        :param dio_number: DIO pin 0...5
        :param callback: The function to call when the DIO triggers an IRQ.
        :return: None
        """
        GPIO.add_event_detect(dio_number, GPIO.RISING, callback=callback)

    def add_events(self,cb_dio0, cb_dio1, cb_dio2, cb_dio3, cb_dio4, cb_dio5, switch_cb=None):
        return
        #self.add_event_detect(self.DIO0, callback=cb_dio0)
        #self.add_event_detect(self.DIO5, callback=cb_dio5)

    def led_on(self,value=1):
        """ Switch the proto shields LED
        :param value: 0/1 for off/on. Default is 1.
        :return: value
        :rtype : int
        """
        GPIO.output(self.LED, value)
        return value

    def led_off(self):
        """ Switch LED off
        :return: 0
        """
        GPIO.output(self.LED, 0)
        return 0

    def blink(self,time_sec, n_blink):
        if n_blink == 0:
            return
        self.led_on()
        for i in range(n_blink):
            time.sleep(time_sec)
            self.led_off()
            time.sleep(time_sec)
            self.led_on()
        self.led_off()

    def read_gpio(self):
        return (GPIO.input(self.DIO0),GPIO.input(self.DIO5))
