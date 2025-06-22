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

try:
    import alsaaudio
except:
    logging.warning("No alsaaudio - i2s support disabled")

# Allow for testing without a radio
try:
    from SX127x.LoRa import *
    from SX127x.hardware_piloragateway import HardwareInterface
except:
    HardwareInterface = None
    logging.error("Could not load SX127x. modules")

class RFM98W(object):
    """
    RFM98W Wrapper for Wenet Transmission, using 2-FSK Direct-Asynchronous Modulation
    """    
    def __init__(
            self,
            spidevice=0,
            frequency=443.500,
            baudrate=115200,
            tx_power_dbm=17,
            reinit_count=5000,
            led=None
            ):
        
        self.spidevice = spidevice
        self.frequency = frequency
        self.baudrate = baudrate
        self.tx_power_dbm = tx_power_dbm
        self.reinit_count = reinit_count
        
        self.hw = None
        self.lora = None

        self.tx_packet_count = 0

        self.temperature = -999

        self.led = led


    def start(self):
        """
        Initialise (or re-initialise) both the RFM98W and Serial connections.
        Configure the RFM98W into direct asynchronous FSK mode, with the appropriate power, deviation, and transmit frequency.
        """
    
        # Cleanup any open file handlers.
        if self.hw:
            self.hw.teardown()

        if self.led:
            self.hw = HardwareInterface(self.spidevice,LED=self.led)
        else:
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
        self.get_temperature()

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
        self.temperature = self.lora.get_register(0x3c) * (-1)
        if self.temperature < -63:
            self.temperature += 255
        logging.info(f"RFM98W - Temperature: {self.temperature} C")

        return self.temperature

class RFM98W_Serial(RFM98W):
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
        
        self.serial_port = serial_port

        super().__init__(spidevice,frequency,baudrate,tx_power_dbm,reinit_count)
        self.start()
    

    def start(self):
        """
        Initialise (or re-initialise) both the RFM98W and Serial connections.
        Configure the RFM98W into direct asynchronous FSK mode, with the appropriate power, deviation, and transmit frequency.
        """
        super().start()
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
        super().shutdown()
        try:
            # Close the serial connection
            self.serial.close()
            logging.info("RFM98W - Closed Serial Port")
            self.serial = None
        except:
            pass

        return

    
    def transmit_packet(self, packet):
        """
        Modulate serial data, using a UART.
        """
        if self.serial:
            self.serial.write(packet)

        super().transmit_packet(packet) # used to reinit the radio occasionally


class RFM98W_I2S(RFM98W):
    """
    RFM98W Wrapper for Wenet Transmission, using 2-FSK Direct-Asynchronous Modulation via a I2S.
    """

    def __init__(
            self,
            spidevice=0,
            baudrate=96000,
            frequency=443.500,
            audio_device="hw:CARD=i2smaster,DEV=0",
            tx_power_dbm=17,
            reinit_count=5000
            ):
        
        self.audio_width = 2 # bytes
        self.audio_rate = 48000
        self.channels = 2

        audio_rates = [8000,16000,22050,44100,48000,96000,176400,192000]
        logging.debug(f"Searching for best audio sample rate for {baudrate}")

        # This is a naive approach and there are totally more options avaliable to us than this.
        # We also aren't strictly limited to just whole bytes for sretching the time, however that's easiest.

        for self.audio_rate in audio_rates:
            self.audio_bit_rate = self.audio_rate * self.channels * (self.audio_width*8)
            self.bytes_per_bit = self.audio_bit_rate//baudrate//8
            try:
                actual_rf_bitrate = self.audio_bit_rate/(self.bytes_per_bit*8)
            except ZeroDivisionError:
                logging.debug(f"NO - {self.audio_rate}")
                continue
            if (self.audio_bit_rate/baudrate)%8 != 0:
                logging.debug(f"NO - {self.audio_rate} RF bitrate = {actual_rf_bitrate}")
            else:
                logging.debug(f"YES - RF bitrate = {actual_rf_bitrate} Audio bitrate = {self.audio_bit_rate} Audio samplerate = {self.audio_rate} Audio Bytes Per Modem Bit = {self.bytes_per_bit}")
                break
        else:
            logging.critical("Exhausted all audio sample rates")
            raise ValueError("Baudrate not suitable for soundcard.")


        # fixed baudrate for the moment
        super().__init__(spidevice,frequency,baudrate,tx_power_dbm,reinit_count,led=5) # can't use 21 for LED as I2S is there
        
        

       

        if (
            ((self.audio_rate * self.channels * self.audio_width * 8) / self.baudrate)%8 !=0
        ):
            raise ValueError(f"Not aligned audio rate. Must be a whole byte per bit. audio_rate: {self.audio_rate} rate: {self.baudrate}")

      

        self.audio_device = audio_device
        self.precompute_bytes()
        self.periodsize = None
        self.pcm = None

        self.start()
        

    def start(self):
        """
        Initialise (or re-initialise) both the RFM98W and Serial connections.
        Configure the RFM98W into direct asynchronous FSK mode, with the appropriate power, deviation, and transmit frequency.
        """

        super().start()
        
        # Now initialise the Serial port for modulation
        if self.audio_device and alsaaudio and not self.pcm:
            try: 
                self.pcm = alsaaudio.PCM(device=self.audio_device)
                logging.info(f"RFM98W - Opened audio device {self.pcm.cardname()} for modulation.")
                if self.pcm.setrate(self.audio_rate) != self.audio_rate:
                    logging.critical("Could not set correct audio rate for datarate")
                if self.pcm.setchannels(self.channels) != self.channels:
                    logging.critical("could not set channel number")
            except Exception as e:
                logging.critical(f"Could not open audio device! Error: {str(e)}")
        elif not self.pcm:
            logging.error("No alsaaudio - debugging mode")
            self.pcm = BinaryDebug()


    def precompute_bytes(self):
        logging.debug("Precomputing byte lookup table")
        self.byte_to_i2s_bytes ={}
        for x in range(256):
            buffer = b''
            for bit_i in range(7,-1,-1):
                 bit = (x >> (bit_i)) & 0b1
                 bit = b'\xff' if bit else b'\x00'
                 buffer = buffer + (bit*self.bytes_per_bit)
            self.byte_to_i2s_bytes[x] = buffer
        logging.debug("Finished creating lookup table")

    def shutdown(self):
        """
        Shutdown the RFM98W, and close the SPI and Serial connections.
        """

        try:
            # Close the audio device
            self.pcm.close()
            logging.info("RFM98W - Closed audio device")
            self.pcm = None
        except:
            pass

        return



    def transmit_packet(self, packet):
        """
        Modulate audio data, using a I2S.
        """
        if self.pcm:
            desired_period_size = (len(packet)*8*self.bytes_per_bit)//self.channels//self.audio_width
            if (
                self.periodsize == None or
                self.periodsize != desired_period_size
            ):
                logging.debug(f"Setting period size to: {desired_period_size}")
                if self.pcm.setperiodsize(desired_period_size) != desired_period_size:
                        logging.critical(f"could not set period size to match packet size: got {self.pcm.setperiodsize(desired_period_size)}")
                else:
                    self.periodsize = desired_period_size
                    logging.debug(f"Period size set")
            buffer = b''
            for i_byte in packet:
                buffer = buffer + self.byte_to_i2s_bytes[i_byte]
            frame_length = (len(buffer)//self.channels//self.audio_width)
            if frame_length % self.periodsize != 0:
                logging.critical(f"buffer frames length {frame_length} != periodsize {self.periodsize}")
            self.pcm.write(buffer)

        super().transmit_packet(packet) # used to reinit the radio occasionally

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
            d_array = np.unpackbits(np.frombuffer(bytes([d]),dtype=np.uint8))
            raw_data = np.concatenate((raw_data,[0],d_array[::-1],[1]))

        self.f.write(raw_data.astype(np.uint8).tostring())

    def close(self):
        self.f.close()


if __name__ == '__main__':

    # Test code for the above. Allows enabling a radio and (optionally) sending some test packets.

    import time
    parser = argparse.ArgumentParser()
    parser.add_argument("--rfm98w", default=None, type=int, help="If set, configure a RFM98W on this SPI device number. Using UART")
    parser.add_argument("--rfm98w-i2s", default=None, type=int, help="If set, configure a RFM98W on this SPI device number. Using I2S")
    parser.add_argument("--audio-device", default="hw:CARD=i2smaster,DEV=0", type=str, help="Sets the audio device for rfm98w-i2s mode.")
    parser.add_argument("--frequency", default=443.500, type=float, help="Transmit Frequency (MHz). (Default: 443.500 MHz)")
    parser.add_argument("--baudrate", default=None, type=int, help="Wenet TX baud rate. (Default: 115200 for uart and 96000 for I2S). Known working I2S baudrates: 8000, 24000, 48000, 96000 ")
    parser.add_argument("--serial_port", default="/dev/ttyAMA0", type=str, help="Serial Port for modulation.")
    parser.add_argument("--tx_power", default=17, type=int, help="Transmit power in dBm (Default: 17 dBm, 50mW. Allowed values: 2-17)")
    parser.add_argument("--shutdown", default=False, action="store_true", help="Shutdown Transmitter after configuration.")
    parser.add_argument("--test_modulation", default=False, action="store_true", help="Transmit a sequence of dummy packets as a test.")
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Show additional debug info.")
    args = parser.parse_args()

    if args.baudrate == None:
        if args.rfm98w:
            args.baudrate = 115200
        elif args.rfm98w_i2s:
            args.baudrate = 96000

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
    elif args.rfm98w_i2s is not None:
        radio = RFM98W_I2S(
            spidevice = args.rfm98w,
            baudrate = args.baudrate,
            frequency = args.frequency,
            audio_device= args.audio_device,
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


