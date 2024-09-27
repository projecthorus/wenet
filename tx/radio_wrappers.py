#!/usr/bin/env python
#
# 	Radio Wrappers for Wenet Transmissions
#
#   Copyright (C) 2024  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#	For RFM98W support, requires pySX127x:
#	https://github.com/darksidelemm/pySX127x
#   (This is included with the Wenet repository)
#
#	Uses spidev for comms with a RFM98W module.
#
#	Note: As with the RFM22B version, all this script does
#	is get the RFM98W onto the right frequency, and into the right mode.
#
#	SPI: Connected to CE0 (like most of my LoRa shields)
#	RPi TXD: Connected to RFM98W's DIO2 pin.
#
import sys
import argparse
import logging
import serial
import time
import numpy as np
from SX127x.LoRa import *
from SX127x.hardware_piloragateway import HardwareInterface


class RFM98W_Serial(object):
    """
    RFM98W Wrapper for Wenet Transmission, using 2-FSK Direct-Asynchronous Modulation via a UART.
    """

    def __init__(
            self,
            spidevice=0,
            frequency=443.500,
            baudrate=115200,
            serial_port=None,
            tx_power_dbm=17,
            reinit_count=5000
            ):
        
        self.spidevice = spidevice
        self.frequency = frequency
        self.baudrate = baudrate
        self.serial_port = serial_port
        self.tx_power_dbm = tx_power_dbm
        self.reinit_count = reinit_count
        
        self.hw = None
        self.lora = None

        self.tx_packet_count = 0

        self.temperature = -999

        self.start()
    

    def start(self):
        """
        Initialise (or re-initialise) both the RFM98W and Serial connections.
        Configure the RFM98W into direct asynchronous FSK mode, with the appropriate power, deviation, and transmit frequency.
        """
    
        self.hw = HardwareInterface(self.spidevice)
        self.lora = LoRaRFM98W(self.hw, verbose=False)

        logging.debug(f"RFM98W - SX127x Register Dump: {self.lora.backup_registers}")
        logging.debug(f"RFM98W - SX127x device version: {hex(self.lora.get_version())}")

        if not self.comms_ok():
            logging.critical("RFM98W - No communication with RFM98W IC!")
            self.shutdown()
            return

        # Deviation selection. 
        if self.baudrate == 9600:
            deviation = 4800
        elif self.baudrate == 4800:
            deviation = 2400
        else:
            # Default deviation, for 115200 baud
            deviation = 71797

        # Refer https://cdn.sparkfun.com/assets/learn_tutorials/8/0/4/RFM95_96_97_98W.pdf
        self.lora.set_register(0x01,0x00) # FSK Sleep Mode
        self.lora.set_register(0x31,0x00) # Set Continuous Transmit Mode

        # Get the IC temperature
        self.temperature = self.get_temperature()

        self.lora.set_freq(self.frequency)
        logging.info(f"RFM98W - Frequency set to: {self.frequency} MHz.")

        # Set Deviation (~70 kHz). Signals ends up looking a bit wider than the RFM22B version.
        _dev_lsbs = int(deviation / 61.03)
        _dev_msb = _dev_lsbs >> 8
        _dev_lsb = _dev_lsbs % 256
        self.lora.set_register(0x04,_dev_msb)
        self.lora.set_register(0x05,_dev_lsb)
    
        # Set Transmit power
        tx_power_lookup = {0:0x80, 1:0x80, 2:0x80, 3:0x81, 4:0x82, 5:0x83, 6:0x84, 7:0x85, 8:0x86, 9:0x87, 10:0x88, 11:0x89, 12:0x8A, 13:0x8B, 14:0x8C, 15:0x8D, 16:0x8E, 17:0x8F}
        if self.tx_power_dbm in tx_power_lookup:
            self.lora.set_register(0x09, tx_power_lookup[self.tx_power_dbm])
            logging.info(f"RFM98W - TX Power set to {self.tx_power_dbm} dBm ({hex(tx_power_lookup[self.tx_power_dbm])}).")
        else:
            # Default to low power, 1.5mW or so
            self.lora.set_register(0x09, 0x80)
            logging.info(f"RFM98W - Unknown TX power, setting to 2 dBm (0x80).")

        # Go into TX mode.
        self.lora.set_register(0x01,0x02) # .. via FSTX mode (where the transmit frequency actually gets set)
        self.lora.set_register(0x01,0x03) # Now we're in TX mode...

        # Seems we need to briefly sleep before we can read the register correctly.
        time.sleep(0.1)

        # Confirm we've gone into transmit mode.
        if self.lora.get_register(0x01) == 0x03:
            logging.info("RFM98W - Radio initialised!")
        else:
            logging.critical("RFM98W - TX Mode not set correctly!")
        
        # Now initialise the Serial port for modulation
        if self.serial_port:
            try:
                self.serial = serial.Serial(self.serial_port, self.baudrate)
                logging.info(f"RFM98W - Opened Serial port {self.serial_port} for modulation.")
            except Exception as e:
                logging.critical(f"Could not open serial port! Error: {str(e)}")
                self.serial = None

        else:
            # If no serial port info provided, write out to a binary debug file.
            self.serial = BinaryDebug()
            logging.info("No serial port provided - using Binary Debug output (binary_debug.bin)")



    def shutdown(self):
        """
        Shutdown the RFM98W, and close the SPI and Serial connections.
        """

        try:
            # Set radio into FSK sleep mode
            self.lora.set_register(0x01,0x00)
            logging.info("RFM98W - Set radio into sleep mode.")
            self.lora = None
        except:
            pass

        try:
            # Shutdown SPI device
            self.hw.teardown()
            logging.info("RFM98W - Disconnected from SPI.")
            self.hw = None
        except:
            pass

        try:
            # Close the serial connection
            self.serial.close()
            logging.info("RFM98W - Closed Serial Port")
            self.serial = None
        except:
            pass

        return

    
    def comms_ok(self):
        """
        Test SPI communications with the RFM98W and return true if ok.
        """

        try:
            _ver = self.lora.get_version()

            if _ver == 0x00 or _ver == 0xFF or _ver == None:
                return False
            else:
                return True
        except Exception as e:
            logging.critical("RFM98W - Could not read device version!")
            return False

        return False
    

    def transmit_packet(self, packet):
        """
        Modulate serial data, using a UART.
        """
        if self.serial:
            self.serial.write(packet)

        # Increment transmit packet counter
        self.tx_packet_count += 1

        # If we have a reinitialisation count set, reinitialise the radio.
        if self.reinit_count:
            if self.tx_packet_count % self.reinit_count == 0:
                logging.info(f"RFM98W - Reinitialising Radio at {self.tx_packet_count} packets.")
                self.start()

    def get_temperature(self):
        """
        Get radio module temperature (uncalibrated)
        """
        # Make temperature measurement
        temperature = self.lora.get_register(0x3c) * (-1)
        if temperature < -63:
            temperature += 255
        logging.info(f"RFM98W - Temperature: {self.temperature} C")

        return temperature

class SerialOnly(object):
    """
    Transmitter Wrapper that does not initialise any radios.
    """

    def __init__(
            self,
            baudrate=115200,
            serial_port=None,
            reinit_count=5000
            ):
        
        self.baudrate = baudrate
        self.serial_port = serial_port
        self.reinit_count = reinit_count

        self.tx_packet_count = 0

        self.start()
    

    def start(self):
        """
        Initialise (or re-initialise) the Serial connection.
        """
    
        # Initialise the Serial port for modulation
        if self.serial_port:
            try:
                self.serial = serial.Serial(self.serial_port, self.baudrate)
                logging.info(f"SerialOnly - Opened Serial port {self.serial_port} for modulation.")
            except Exception as e:
                logging.critical(f"SerialOnly - Could not open serial port! Error: {str(e)}")
                self.serial = None

        else:
            # If no serial port info provided, write out to a binary debug file.
            self.serial = BinaryDebug()
            logging.info("SerialOnly - No serial port provided - using Binary Debug output (binary_debug.bin)")



    def shutdown(self):
        """
        Shutdown the Serial connection.
        """
        try:
            # Close the serial connection
            self.serial.close()
            logging.info("SerialOnly - Closed Serial Port")
            self.serial = None
        except:
            pass

        return

    
    def comms_ok(self):
        """
        Dummy function, no radio comms to test.
        """
        return True
    

    def transmit_packet(self, packet):
        """
        Modulate serial data, using a UART.
        """
        if self.serial:
            self.serial.write(packet)

        # Increment transmit packet counter
        self.tx_packet_count += 1

        # If we have a reinitialisation count set, reinitialise the radio.
        if self.reinit_count:
            if self.tx_packet_count % self.reinit_count == 0:
                logging.info(f"SerialOnly - Reinitialising Serial at {self.tx_packet_count} packets.")
                self.start()


class BinaryDebug(object):
    """ Debug binary 'transmitter' Class
    Used to write packet data to a file in one-bit-per-char (i.e. 0 = 0x00, 1 = 0x01)
    format for use with codec2-dev's fsk modulator.
    Useful for debugging, that's about it.
    """
    def __init__(self):
        self.f = open("binary_debug.bin",'wb')

    def write(self,data):
        # TODO: Add in RS232 framing
        raw_data = np.array([],dtype=np.uint8)
        for d in data:
            d_array = np.unpackbits(np.fromstring(d,dtype=np.uint8))
            raw_data = np.concatenate((raw_data,[0],d_array[::-1],[1]))

        self.f.write(raw_data.astype(np.uint8).tostring())

    def close(self):
        self.f.close()


if __name__ == '__main__':

    # Test code for the above. Allows enabling a radio and (optionally) sending some test packets.

    import time
    parser = argparse.ArgumentParser()
    parser.add_argument("--rfm98w", default=None, type=int, help="If set, configure a RFM98W on this SPI device number.")
    parser.add_argument("--frequency", default=443.500, type=float, help="Transmit Frequency (MHz). (Default: 443.500 MHz)")
    parser.add_argument("--baudrate", default=115200, type=int, help="Wenet TX baud rate. (Default: 115200).")
    parser.add_argument("--serial_port", default="/dev/ttyAMA0", type=str, help="Serial Port for modulation.")
    parser.add_argument("--tx_power", default=17, type=int, help="Transmit power in dBm (Default: 17 dBm, 50mW. Allowed values: 2-17)")
    parser.add_argument("--shutdown", default=False, action="store_true", help="Shutdown Transmitter after configuration.")
    parser.add_argument("--test_modulation", default=False, action="store_true", help="Transmit a sequence of dummy packets as a test.")
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Show additional debug info.")
    args = parser.parse_args()

    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    # Set up logging
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging_level)

    radio = None

    if args.rfm98w is not None:
        radio = RFM98W_Serial(
            spidevice = args.rfm98w,
            frequency = args.frequency,
            baudrate = args.baudrate,
            serial_port = args.serial_port,
            tx_power_dbm = args.tx_power
        )
    # Other radio options would go here.
    else:
        logging.critical("No radio type specified! Exiting")
        sys.exit(1)

    if args.test_modulation:
        # Transmit a canned text message a few times
        time.sleep(1)
        test_packet = b'UUUUUUUUUUUUUUUU\xab\xcd\xef\x01\x00\x1d\x00\x01This is a Wenet test message!UUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUUU5\x89\xad5\xff\xfbgX\x96\xaa\x10\xb9\x05,\x8co\xf7\xf0\xdd\x19\x1bs2\xd9$\x85\xa2\xc2\xd5\xc9\x15\xef\xac\x06\xb6\x11H\xb0;\xc3\xae\x1b\xe0_\x8cC\x13L*\x04\x17(\x9a\xa6\x95\x84\xf1UB{\xf5\x96\xb9\x14\x05\xa8@'
        logging.info("Sending 100 test packets.")
        for x in range(100):
            radio.transmit_packet(test_packet)
            time.sleep(0.1)

    if args.shutdown:
        logging.info("Sleeping 5 seconds before shutdown")
        time.sleep(5)
        radio.shutdown()

    sys.exit(0)


