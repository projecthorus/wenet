# Adafruit BNO055 Absolute Orientation Sensor Library
# Copyright (c) 2015 Adafruit Industries
# Author: Tony DiCola
#
# Modifications for Wenet project by Mark Jessop 2017.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import binascii
import logging
import struct
import time
import datetime
import json
import serial
from threading import Thread


# I2C addresses
BNO055_ADDRESS_A                     = 0x28
BNO055_ADDRESS_B                     = 0x29
BNO055_ID                            = 0xA0

# Page id register definition
BNO055_PAGE_ID_ADDR                  = 0X07

# PAGE0 REGISTER DEFINITION START
BNO055_CHIP_ID_ADDR                  = 0x00
BNO055_ACCEL_REV_ID_ADDR             = 0x01
BNO055_MAG_REV_ID_ADDR               = 0x02
BNO055_GYRO_REV_ID_ADDR              = 0x03
BNO055_SW_REV_ID_LSB_ADDR            = 0x04
BNO055_SW_REV_ID_MSB_ADDR            = 0x05
BNO055_BL_REV_ID_ADDR                = 0X06

# Accel data register
BNO055_ACCEL_DATA_X_LSB_ADDR         = 0X08
BNO055_ACCEL_DATA_X_MSB_ADDR         = 0X09
BNO055_ACCEL_DATA_Y_LSB_ADDR         = 0X0A
BNO055_ACCEL_DATA_Y_MSB_ADDR         = 0X0B
BNO055_ACCEL_DATA_Z_LSB_ADDR         = 0X0C
BNO055_ACCEL_DATA_Z_MSB_ADDR         = 0X0D

# Mag data register
BNO055_MAG_DATA_X_LSB_ADDR           = 0X0E
BNO055_MAG_DATA_X_MSB_ADDR           = 0X0F
BNO055_MAG_DATA_Y_LSB_ADDR           = 0X10
BNO055_MAG_DATA_Y_MSB_ADDR           = 0X11
BNO055_MAG_DATA_Z_LSB_ADDR           = 0X12
BNO055_MAG_DATA_Z_MSB_ADDR           = 0X13

# Gyro data registers
BNO055_GYRO_DATA_X_LSB_ADDR          = 0X14
BNO055_GYRO_DATA_X_MSB_ADDR          = 0X15
BNO055_GYRO_DATA_Y_LSB_ADDR          = 0X16
BNO055_GYRO_DATA_Y_MSB_ADDR          = 0X17
BNO055_GYRO_DATA_Z_LSB_ADDR          = 0X18
BNO055_GYRO_DATA_Z_MSB_ADDR          = 0X19

# Euler data registers
BNO055_EULER_H_LSB_ADDR              = 0X1A
BNO055_EULER_H_MSB_ADDR              = 0X1B
BNO055_EULER_R_LSB_ADDR              = 0X1C
BNO055_EULER_R_MSB_ADDR              = 0X1D
BNO055_EULER_P_LSB_ADDR              = 0X1E
BNO055_EULER_P_MSB_ADDR              = 0X1F

# Quaternion data registers
BNO055_QUATERNION_DATA_W_LSB_ADDR    = 0X20
BNO055_QUATERNION_DATA_W_MSB_ADDR    = 0X21
BNO055_QUATERNION_DATA_X_LSB_ADDR    = 0X22
BNO055_QUATERNION_DATA_X_MSB_ADDR    = 0X23
BNO055_QUATERNION_DATA_Y_LSB_ADDR    = 0X24
BNO055_QUATERNION_DATA_Y_MSB_ADDR    = 0X25
BNO055_QUATERNION_DATA_Z_LSB_ADDR    = 0X26
BNO055_QUATERNION_DATA_Z_MSB_ADDR    = 0X27

# Linear acceleration data registers
BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR  = 0X28
BNO055_LINEAR_ACCEL_DATA_X_MSB_ADDR  = 0X29
BNO055_LINEAR_ACCEL_DATA_Y_LSB_ADDR  = 0X2A
BNO055_LINEAR_ACCEL_DATA_Y_MSB_ADDR  = 0X2B
BNO055_LINEAR_ACCEL_DATA_Z_LSB_ADDR  = 0X2C
BNO055_LINEAR_ACCEL_DATA_Z_MSB_ADDR  = 0X2D

# Gravity data registers
BNO055_GRAVITY_DATA_X_LSB_ADDR       = 0X2E
BNO055_GRAVITY_DATA_X_MSB_ADDR       = 0X2F
BNO055_GRAVITY_DATA_Y_LSB_ADDR       = 0X30
BNO055_GRAVITY_DATA_Y_MSB_ADDR       = 0X31
BNO055_GRAVITY_DATA_Z_LSB_ADDR       = 0X32
BNO055_GRAVITY_DATA_Z_MSB_ADDR       = 0X33

# Temperature data register
BNO055_TEMP_ADDR                     = 0X34

# Status registers
BNO055_CALIB_STAT_ADDR               = 0X35
BNO055_SELFTEST_RESULT_ADDR          = 0X36
BNO055_INTR_STAT_ADDR                = 0X37

BNO055_SYS_CLK_STAT_ADDR             = 0X38
BNO055_SYS_STAT_ADDR                 = 0X39
BNO055_SYS_ERR_ADDR                  = 0X3A

# Unit selection register
BNO055_UNIT_SEL_ADDR                 = 0X3B
BNO055_DATA_SELECT_ADDR              = 0X3C

# Mode registers
BNO055_OPR_MODE_ADDR                 = 0X3D
BNO055_PWR_MODE_ADDR                 = 0X3E

BNO055_SYS_TRIGGER_ADDR              = 0X3F
BNO055_TEMP_SOURCE_ADDR              = 0X40

# Axis remap registers
BNO055_AXIS_MAP_CONFIG_ADDR          = 0X41
BNO055_AXIS_MAP_SIGN_ADDR            = 0X42

# Axis remap values
AXIS_REMAP_X                         = 0x00
AXIS_REMAP_Y                         = 0x01
AXIS_REMAP_Z                         = 0x02
AXIS_REMAP_POSITIVE                  = 0x00
AXIS_REMAP_NEGATIVE                  = 0x01

# SIC registers
BNO055_SIC_MATRIX_0_LSB_ADDR         = 0X43
BNO055_SIC_MATRIX_0_MSB_ADDR         = 0X44
BNO055_SIC_MATRIX_1_LSB_ADDR         = 0X45
BNO055_SIC_MATRIX_1_MSB_ADDR         = 0X46
BNO055_SIC_MATRIX_2_LSB_ADDR         = 0X47
BNO055_SIC_MATRIX_2_MSB_ADDR         = 0X48
BNO055_SIC_MATRIX_3_LSB_ADDR         = 0X49
BNO055_SIC_MATRIX_3_MSB_ADDR         = 0X4A
BNO055_SIC_MATRIX_4_LSB_ADDR         = 0X4B
BNO055_SIC_MATRIX_4_MSB_ADDR         = 0X4C
BNO055_SIC_MATRIX_5_LSB_ADDR         = 0X4D
BNO055_SIC_MATRIX_5_MSB_ADDR         = 0X4E
BNO055_SIC_MATRIX_6_LSB_ADDR         = 0X4F
BNO055_SIC_MATRIX_6_MSB_ADDR         = 0X50
BNO055_SIC_MATRIX_7_LSB_ADDR         = 0X51
BNO055_SIC_MATRIX_7_MSB_ADDR         = 0X52
BNO055_SIC_MATRIX_8_LSB_ADDR         = 0X53
BNO055_SIC_MATRIX_8_MSB_ADDR         = 0X54

# Accelerometer Offset registers
ACCEL_OFFSET_X_LSB_ADDR              = 0X55
ACCEL_OFFSET_X_MSB_ADDR              = 0X56
ACCEL_OFFSET_Y_LSB_ADDR              = 0X57
ACCEL_OFFSET_Y_MSB_ADDR              = 0X58
ACCEL_OFFSET_Z_LSB_ADDR              = 0X59
ACCEL_OFFSET_Z_MSB_ADDR              = 0X5A

# Magnetometer Offset registers
MAG_OFFSET_X_LSB_ADDR                = 0X5B
MAG_OFFSET_X_MSB_ADDR                = 0X5C
MAG_OFFSET_Y_LSB_ADDR                = 0X5D
MAG_OFFSET_Y_MSB_ADDR                = 0X5E
MAG_OFFSET_Z_LSB_ADDR                = 0X5F
MAG_OFFSET_Z_MSB_ADDR                = 0X60

# Gyroscope Offset register s
GYRO_OFFSET_X_LSB_ADDR               = 0X61
GYRO_OFFSET_X_MSB_ADDR               = 0X62
GYRO_OFFSET_Y_LSB_ADDR               = 0X63
GYRO_OFFSET_Y_MSB_ADDR               = 0X64
GYRO_OFFSET_Z_LSB_ADDR               = 0X65
GYRO_OFFSET_Z_MSB_ADDR               = 0X66

# Radius registers
ACCEL_RADIUS_LSB_ADDR                = 0X67
ACCEL_RADIUS_MSB_ADDR                = 0X68
MAG_RADIUS_LSB_ADDR                  = 0X69
MAG_RADIUS_MSB_ADDR                  = 0X6A

# Power modes
POWER_MODE_NORMAL                    = 0X00
POWER_MODE_LOWPOWER                  = 0X01
POWER_MODE_SUSPEND                   = 0X02

# Operation mode settings
OPERATION_MODE_CONFIG                = 0X00
OPERATION_MODE_ACCONLY               = 0X01
OPERATION_MODE_MAGONLY               = 0X02
OPERATION_MODE_GYRONLY               = 0X03
OPERATION_MODE_ACCMAG                = 0X04
OPERATION_MODE_ACCGYRO               = 0X05
OPERATION_MODE_MAGGYRO               = 0X06
OPERATION_MODE_AMG                   = 0X07
OPERATION_MODE_IMUPLUS               = 0X08
OPERATION_MODE_COMPASS               = 0X09
OPERATION_MODE_M4G                   = 0X0A
OPERATION_MODE_NDOF_FMC_OFF          = 0X0B
OPERATION_MODE_NDOF                  = 0X0C


logger = logging.getLogger(__name__)


class BNO055(object):

    def __init__(self, rst=None, address=BNO055_ADDRESS_A, i2c=None, gpio=None,
                 serial_port=None, serial_timeout_sec=5, **kwargs):
        # If reset pin is provided save it and a reference to provided GPIO
        # bus (or the default system GPIO bus if none is provided).
        self._rst = rst
        if self._rst is not None:
            if gpio is None:
                import Adafruit_GPIO as GPIO
                gpio = GPIO.get_platform_gpio()
            self._gpio = gpio
            # Setup the reset pin as an output at a high level.
            self._gpio.setup(self._rst, GPIO.OUT)
            self._gpio.set_high(self._rst)
            # Wait a 650 milliseconds in case setting the reset high reset the chip.
            time.sleep(0.65)
        self._serial = None
        self._i2c_device = None
        if serial_port is not None:
            # Use serial communication if serial_port name is provided.
            # Open the serial port at 115200 baud, 8N1.  Add a 5 second timeout
            # to prevent hanging if device is disconnected.
            self._serial = serial.Serial(serial_port, 115200, timeout=serial_timeout_sec)
        else:
            # Use I2C if no serial port is provided.
            # Assume we're using platform's default I2C bus if none is specified.
            if i2c is None:
                import Adafruit_GPIO.I2C as I2C
                i2c = I2C
            # Save a reference to the I2C device instance for later communication.
            self._i2c_device = i2c.get_i2c_device(address, **kwargs)

    def close(self):
        try:
            if self._serial != None:
                self._serial.close()

            if self._i2c_device != None:
                self._i2c_device.close()
        except Exception as e:
            print(str(e))

    def _serial_send(self, command, ack=True, max_attempts=5):
        # Send a serial command and automatically handle if it needs to be resent
        # because of a bus error.  If ack is True then an ackowledgement is
        # expected and only up to the maximum specified attempts will be made
        # to get a good acknowledgement (default is 5).  If ack is False then
        # no acknowledgement is expected (like when resetting the device).
        attempts = 0
        while True:
            # Flush any pending received data to get into a clean state.
            self._serial.flushInput()
            # Send the data.
            self._serial.write(command)
            logger.debug('Serial send: 0x{0}'.format(binascii.hexlify(command)))
            # Stop if no acknowledgment is expected.
            if not ack:
                return
            # Read acknowledgement response (2 bytes).
            resp = bytearray(self._serial.read(2))
            logger.debug('Serial receive: 0x{0}'.format(binascii.hexlify(resp)))
            if resp is None or len(resp) != 2:
                raise RuntimeError('Timeout waiting for serial acknowledge, is the BNO055 connected?')
            # Stop if there's no bus error (0xEE07 response) and return response bytes.
            if not (resp[0] == 0xEE and resp[1] == 0x07):
                return resp
            # Else there was a bus error so resend, as recommended in UART app
            # note at:
            #   http://ae-bst.resource.bosch.com/media/products/dokumente/bno055/BST-BNO055-AN012-00.pdf
            attempts += 1
            if attempts >=  max_attempts:
                raise RuntimeError('Exceeded maximum attempts to acknowledge serial command without bus error!')

    def _write_bytes(self, address, data, ack=True):
        # Write a list of 8-bit values starting at the provided register address.
        if self._i2c_device is not None:
            # I2C write.
            self._i2c_device.writeList(address, data)
        else:
            # Build and send serial register write command.
            command = bytearray(4+len(data))
            command[0] = 0xAA  # Start byte
            command[1] = 0x00  # Write
            command[2] = address & 0xFF
            command[3] = len(data) & 0xFF
            command[4:] = map(lambda x: x & 0xFF, data)
            resp = self._serial_send(command, ack=ack)
            # Verify register write succeeded if there was an acknowledgement.
            if resp[0] != 0xEE and resp[1] != 0x01:
                raise RuntimeError('Register write error: 0x{0}'.format(binascii.hexlify(resp)))

    def _write_byte(self, address, value, ack=True):
        # Write an 8-bit value to the provided register address.  If ack is True
        # then expect an acknowledgement in serial mode, otherwise ignore any
        # acknowledgement (necessary when resetting the device).
        if self._i2c_device is not None:
            # I2C write.
            self._i2c_device.write8(address, value)
        else:
            # Build and send serial register write command.
            command = bytearray(5)
            command[0] = 0xAA  # Start byte
            command[1] = 0x00  # Write
            command[2] = address & 0xFF
            command[3] = 1     # Length (1 byte)
            command[4] = value & 0xFF
            resp = self._serial_send(command, ack=ack)
            # Verify register write succeeded if there was an acknowledgement.
            if ack and resp[0] != 0xEE and resp[1] != 0x01:
                raise RuntimeError('Register write error: 0x{0}'.format(binascii.hexlify(resp)))

    def _read_bytes(self, address, length):
        # Read a number of unsigned byte values starting from the provided address.
        if self._i2c_device is not None:
            # I2C read.
            return bytearray(self._i2c_device.readList(address, length))
        else:
            # Build and send serial register read command.
            command = bytearray(4)
            command[0] = 0xAA  # Start byte
            command[1] = 0x01  # Read
            command[2] = address & 0xFF
            command[3] = length & 0xFF
            resp = self._serial_send(command)
            # Verify register read succeeded.
            if resp[0] != 0xBB:
                 raise RuntimeError('Register read error: 0x{0}'.format(binascii.hexlify(resp)))
            # Read the returned bytes.
            length = resp[1]
            resp = bytearray(self._serial.read(length))
            logger.debug('Received: 0x{0}'.format(binascii.hexlify(resp)))
            if resp is None or len(resp) != length:
                raise RuntimeError('Timeout waiting to read data, is the BNO055 connected?')
            return resp

    def _read_byte(self, address):
        # Read an 8-bit unsigned value from the provided register address.
        if self._i2c_device is not None:
            # I2C read.
            return self._i2c_device.readU8(address)
        else:
            return self._read_bytes(address, 1)[0]

    def _read_signed_byte(self, address):
        # Read an 8-bit signed value from the provided register address.
        data = self._read_byte(address)
        if data > 127:
            return data - 256
        else:
            return data

    def _config_mode(self):
        # Enter configuration mode.
        self.set_mode(OPERATION_MODE_CONFIG)

    def _operation_mode(self):
        # Enter operation mode to read sensor data.
        self.set_mode(self._mode)

    def begin(self, mode=OPERATION_MODE_NDOF, reset=True):
        """Initialize the BNO055 sensor.  Must be called once before any other
        BNO055 library functions.  Will return True if the BNO055 was
        successfully initialized, and False otherwise.
        """
        # Save the desired normal operation mode.
        self._mode = mode
        # First send a thow-away command and ignore any response or I2C errors
        # just to make sure the BNO is in a good state and ready to accept
        # commands (this seems to be necessary after a hard power down).
        try:
            self._write_byte(BNO055_PAGE_ID_ADDR, 0, ack=False)
        except IOError:
            # Swallow an IOError that might be raised by an I2C issue.  Only do
            # this for this very first command to help get the BNO and board's
            # I2C into a clear state ready to accept the next commands.
            pass
        # Make sure we're in config mode and on page 0.
        self._config_mode()
        self._write_byte(BNO055_PAGE_ID_ADDR, 0)
        # Check the chip ID
        bno_id = self._read_byte(BNO055_CHIP_ID_ADDR)
        logger.debug('Read chip ID: 0x{0:02X}'.format(bno_id))
        if bno_id != BNO055_ID:
            return False
        # Reset the device (if we need to)
        if reset:
            if self._rst is not None:
                # Use the hardware reset pin if provided.
                # Go low for a short period, then high to signal a reset.
                self._gpio.set_low(self._rst)
                time.sleep(0.01)  # 10ms
                self._gpio.set_high(self._rst)
            else:
                # Else use the reset command.  Note that ack=False is sent because
                # the chip doesn't seem to ack a reset in serial mode (by design?).
                self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x20, ack=False)
        # Wait 650ms after reset for chip to be ready (as suggested
        # in datasheet).
        time.sleep(0.65)
        # Set to normal power mode.
        self._write_byte(BNO055_PWR_MODE_ADDR, POWER_MODE_NORMAL)
        # Default to internal oscillator.
        self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x0)
        # Enter normal operation mode.
        self._operation_mode()
        return True

    def set_mode(self, mode):
        """Set operation mode for BNO055 sensor.  Mode should be a value from
        table 3-3 and 3-5 of the datasheet:
          http://www.adafruit.com/datasheets/BST_BNO055_DS000_12.pdf
        """
        self._write_byte(BNO055_OPR_MODE_ADDR, mode & 0xFF)
        # Delay for 30 milliseconds (datsheet recommends 19ms, but a little more
        # can't hurt and the kernel is going to spend some unknown amount of time
        # too).
        time.sleep(0.03)

    def get_revision(self):
        """Return a tuple with revision information about the BNO055 chip.  Will
        return 5 values:
          - Software revision
          - Bootloader version
          - Accelerometer ID
          - Magnetometer ID
          - Gyro ID
        """
        # Read revision values.
        accel = self._read_byte(BNO055_ACCEL_REV_ID_ADDR)
        mag = self._read_byte(BNO055_MAG_REV_ID_ADDR)
        gyro = self._read_byte(BNO055_GYRO_REV_ID_ADDR)
        bl = self._read_byte(BNO055_BL_REV_ID_ADDR)
        sw_lsb = self._read_byte(BNO055_SW_REV_ID_LSB_ADDR)
        sw_msb = self._read_byte(BNO055_SW_REV_ID_MSB_ADDR)
        sw = ((sw_msb << 8) | sw_lsb) & 0xFFFF
        # Return the results as a tuple of all 5 values.
        return (sw, bl, accel, mag, gyro)

    def set_external_crystal(self, external_crystal):
        """Set if an external crystal is being used by passing True, otherwise
        use the internal oscillator by passing False (the default behavior).
        """
        # Switch to configuration mode.
        self._config_mode()
        # Set the clock bit appropriately in the SYS_TRIGGER register.
        if external_crystal:
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x80)
        else:
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x00)
        # Go back to normal operation mode.
        self._operation_mode()

    def get_system_status(self, run_self_test=True):
        """Return a tuple with status information.  Three values will be returned:
          - System status register value with the following meaning:
              0 = Idle
              1 = System Error
              2 = Initializing Peripherals
              3 = System Initialization
              4 = Executing Self-Test
              5 = Sensor fusion algorithm running
              6 = System running without fusion algorithms
          - Self test result register value with the following meaning:
              Bit value: 1 = test passed, 0 = test failed
              Bit 0 = Accelerometer self test
              Bit 1 = Magnetometer self test
              Bit 2 = Gyroscope self test
              Bit 3 = MCU self test
              Value of 0x0F = all good!
          - System error register value with the following meaning:
              0 = No error
              1 = Peripheral initialization error
              2 = System initialization error
              3 = Self test result failed
              4 = Register map value out of range
              5 = Register map address out of range
              6 = Register map write error
              7 = BNO low power mode not available for selected operation mode
              8 = Accelerometer power mode not available
              9 = Fusion algorithm configuration error
             10 = Sensor configuration error

        If run_self_test is passed in as False then no self test is performed and
        None will be returned for the self test result.  Note that running a
        self test requires going into config mode which will stop the fusion
        engine from running.
        """
        self_test = None
        if run_self_test:
            # Switch to configuration mode if running self test.
            self._config_mode()
            # Perform a self test.
            sys_trigger = self._read_byte(BNO055_SYS_TRIGGER_ADDR)
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, sys_trigger | 0x1)
            # Wait for self test to finish.
            time.sleep(1.0)
            # Read test result.
            self_test = self._read_byte(BNO055_SELFTEST_RESULT_ADDR)
            # Go back to operation mode.
            self._operation_mode()
        # Now read status and error registers.
        status = self._read_byte(BNO055_SYS_STAT_ADDR)
        error = self._read_byte(BNO055_SYS_ERR_ADDR)
        # Return the results as a tuple of all 3 values.
        return (status, self_test, error)

    def get_calibration_status(self):
        """Read the calibration status of the sensors and return a 4 tuple with
        calibration status as follows:
          - System, 3=fully calibrated, 0=not calibrated
          - Gyroscope, 3=fully calibrated, 0=not calibrated
          - Accelerometer, 3=fully calibrated, 0=not calibrated
          - Magnetometer, 3=fully calibrated, 0=not calibrated
        """
        # Return the calibration status register value.
        cal_status = self._read_byte(BNO055_CALIB_STAT_ADDR)
        sys = (cal_status >> 6) & 0x03
        gyro = (cal_status >> 4) & 0x03
        accel = (cal_status >> 2) & 0x03
        mag = cal_status & 0x03
        # Return the results as a tuple of all 3 values.
        return (sys, gyro, accel, mag)

    def get_calibration(self):
        """Return the sensor's calibration data and return it as an array of
        22 bytes. Can be saved and then reloaded with the set_calibration function
        to quickly calibrate from a previously calculated set of calibration data.
        """
        # Switch to configuration mode, as mentioned in section 3.10.4 of datasheet.
        self._config_mode()
        # Read the 22 bytes of calibration data and convert it to a list (from
        # a bytearray) so it's more easily serialized should the caller want to
        # store it.
        cal_data = list(self._read_bytes(ACCEL_OFFSET_X_LSB_ADDR, 22))
        # Go back to normal operation mode.
        self._operation_mode()
        return cal_data

    def set_calibration(self, data):
        """Set the sensor's calibration data using a list of 22 bytes that
        represent the sensor offsets and calibration data.  This data should be
        a value that was previously retrieved with get_calibration (and then
        perhaps persisted to disk or other location until needed again).
        """
        # Check that 22 bytes were passed in with calibration data.
        if data is None or len(data) != 22:
            raise ValueError('Expected a list of 22 bytes for calibration data.')
        # Switch to configuration mode, as mentioned in section 3.10.4 of datasheet.
        self._config_mode()
        # Set the 22 bytes of calibration data.
        self._write_bytes(ACCEL_OFFSET_X_LSB_ADDR, data)
        # Go back to normal operation mode.
        self._operation_mode()

    def get_axis_remap(self):
        """Return a tuple with the axis remap register values.  This will return
        6 values with the following meaning:
          - X axis remap (a value of AXIS_REMAP_X, AXIS_REMAP_Y, or AXIS_REMAP_Z.
                          which indicates that the physical X axis of the chip
                          is remapped to a different axis)
          - Y axis remap (see above)
          - Z axis remap (see above)
          - X axis sign (a value of AXIS_REMAP_POSITIVE or AXIS_REMAP_NEGATIVE
                         which indicates if the X axis values should be positive/
                         normal or negative/inverted.  The default is positive.)
          - Y axis sign (see above)
          - Z axis sign (see above)

        Note that by default the axis orientation of the BNO chip looks like
        the following (taken from section 3.4, page 24 of the datasheet).  Notice
        the dot in the corner that corresponds to the dot on the BNO chip:

                           | Z axis
                           |
                           |   / X axis
                       ____|__/____
          Y axis     / *   | /    /|
          _________ /______|/    //
                   /___________ //
                  |____________|/
        """
        # Get the axis remap register value.
        map_config = self._read_byte(BNO055_AXIS_MAP_CONFIG_ADDR)
        z = (map_config >> 4) & 0x03
        y = (map_config >> 2) & 0x03
        x = map_config & 0x03
        # Get the axis remap sign register value.
        sign_config = self._read_byte(BNO055_AXIS_MAP_SIGN_ADDR)
        x_sign = (sign_config >> 2) & 0x01
        y_sign = (sign_config >> 1) & 0x01
        z_sign = sign_config & 0x01
        # Return the results as a tuple of all 3 values.
        return (x, y, z, x_sign, y_sign, z_sign)

    def set_axis_remap(self, x, y, z,
                       x_sign=AXIS_REMAP_POSITIVE, y_sign=AXIS_REMAP_POSITIVE,
                       z_sign=AXIS_REMAP_POSITIVE):
        """Set axis remap for each axis.  The x, y, z parameter values should
        be set to one of AXIS_REMAP_X, AXIS_REMAP_Y, or AXIS_REMAP_Z and will
        change the BNO's axis to represent another axis.  Note that two axises
        cannot be mapped to the same axis, so the x, y, z params should be a
        unique combination of AXIS_REMAP_X, AXIS_REMAP_Y, AXIS_REMAP_Z values.

        The x_sign, y_sign, z_sign values represent if the axis should be positive
        or negative (inverted).

        See the get_axis_remap documentation for information on the orientation
        of the axises on the chip, and consult section 3.4 of the datasheet.
        """
        # Switch to configuration mode.
        self._config_mode()
        # Set the axis remap register value.
        map_config = 0x00
        map_config |= (z & 0x03) << 4
        map_config |= (y & 0x03) << 2
        map_config |= x & 0x03
        self._write_byte(BNO055_AXIS_MAP_CONFIG_ADDR, map_config)
        # Set the axis remap sign register value.
        sign_config = 0x00
        sign_config |= (x_sign & 0x01) << 2
        sign_config |= (y_sign & 0x01) << 1
        sign_config |= z_sign & 0x01
        self._write_byte(BNO055_AXIS_MAP_SIGN_ADDR, sign_config)
        # Go back to normal operation mode.
        self._operation_mode()

    def _read_vector(self, address, count=3):
        # Read count number of 16-bit signed values starting from the provided
        # address. Returns a tuple of the values that were read.
        data = self._read_bytes(address, count*2)
        result = [0]*count
        for i in range(count):
            result[i] = ((data[i*2+1] << 8) | data[i*2]) & 0xFFFF
            if result[i] > 32767:
                result[i] -= 65536
        return result

    def read_euler(self):
        """Return the current absolute orientation as a tuple of heading, roll,
        and pitch euler angles in degrees.
        """
        heading, roll, pitch = self._read_vector(BNO055_EULER_H_LSB_ADDR)
        return (heading/16.0, roll/16.0, pitch/16.0)

    def read_magnetometer(self):
        """Return the current magnetometer reading as a tuple of X, Y, Z values
        in micro-Teslas.
        """
        x, y, z = self._read_vector(BNO055_MAG_DATA_X_LSB_ADDR)
        return (x/16.0, y/16.0, z/16.0)

    def read_gyroscope(self):
        """Return the current gyroscope (angular velocity) reading as a tuple of
        X, Y, Z values in degrees per second.
        """
        x, y, z = self._read_vector(BNO055_GYRO_DATA_X_LSB_ADDR)
        return (x/900.0, y/900.0, z/900.0)

    def read_accelerometer(self):
        """Return the current accelerometer reading as a tuple of X, Y, Z values
        in meters/second^2.
        """
        x, y, z = self._read_vector(BNO055_ACCEL_DATA_X_LSB_ADDR)
        return (x/100.0, y/100.0, z/100.0)

    def read_linear_acceleration(self):
        """Return the current linear acceleration (acceleration from movement,
        not from gravity) reading as a tuple of X, Y, Z values in meters/second^2.
        """
        x, y, z = self._read_vector(BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR)
        return (x/100.0, y/100.0, z/100.0)

    def read_gravity(self):
        """Return the current gravity acceleration reading as a tuple of X, Y, Z
        values in meters/second^2.
        """
        x, y, z = self._read_vector(BNO055_GRAVITY_DATA_X_LSB_ADDR)
        return (x/100.0, y/100.0, z/100.0)

    def read_quaternion(self):
        """Return the current orientation as a tuple of X, Y, Z, W quaternion
        values.
        """
        w, x, y, z = self._read_vector(BNO055_QUATERNION_DATA_W_LSB_ADDR, 4)
        # Scale values, see 3.6.5.5 in the datasheet.
        scale = (1.0 / (1<<14))
        return (x*scale, y*scale, z*scale, w*scale)

    def read_temp(self):
        """Return the current temperature in Celsius."""
        return self._read_signed_byte(BNO055_TEMP_ADDR)

class WenetBNO055(object):
    """ Wenet BNO055 Absolute Orientation Sensor Abstraction Layer """

    # Internal state dictionary, which is updated at a user-defined rate.
    state = {
        # BNO055 Status Information
        'sys_status':   0,
        'sys_error':    0,
        'sys_cal':      0,
        'gyro_cal':     0,
        'accel_cal':    0,
        'magnet_cal':   0,
        'temp':         0,
        # Euler Angles (degrees)
        'euler_heading':    0.0,
        'euler_roll':       0.0,
        'euler_pitch':      0.0,
        # Magnetometer Data (micro-Teslas)
        'magnet_x':     0.0,
        'magnet_y':     0.0,
        'magnet_z':     0.0,
        # Gyroscope Data (Degrees/second)
        'gyro_x':       0.0,
        'gyro_y':       0.0,
        'gyro_z':       0.0,
        # Accelerometer Data (m/s^2)
        'accel_x':      0.0,
        'accel_y':      0.0,
        'accel_z':      0.0,
        # Linear Acceleration Data (m/s^2)
        'linear_accel_x':   0.0,
        'linear_accel_y':   0.0,
        'linear_accel_z':   0.0,
        # Gravity Acceleration Data (m/s^2)
        'gravity_accel_x':  0.0,
        'gravity_accel_y':  0.0,
        'gravity_accel_z':  0.0,
        # Quaternion Data (unit-less)
        'quaternion_x': 0.0,
        'quaternion_y': 0.0,
        'quaternion_z': 0.0,
        'quaternion_w': 0.0,
        # Validity flag. We set this to false as soon as we encounter a serial connection drop.
        'valid':    False,
        # Are we capturing raw sensor data as well as just the euler/quaternion data?
        'raw_sensor_data': False
    }

    # Local storage of calibration data, in case of USB connection reset.
    calibration_data = None

    # Adafruit BNO055 object.
    bno = None

    def __init__(self,
        port='/dev/bno',
        update_rate_hz = 10,
        callback = None,
        callback_decimation = 1,
        debug_ptr = None,
        log_file = None,
        raw_sensor_data = False
        ):
        """ Initialise a WenetBNO055 Abstraction layer Object 

        Keyword Arguments:
        port:   Serial port where the BNO055 is connected. The default baud rate of 115200 baud will be used.
                See 99-usb-serial.rules for suitable udev rules to make a /dev/bno symlink.
        update_rate_hz: The rate at which the internal state vector is updated, in Hz.
                        NOTE: Deprecated. We now update as fast as we can.

        callback: reference to a callback function that will be passed a copy of the above
                  state dictionary at a user-defined rate.
                  NOTE: The callback will be called in a separate thread.
        callback_decimation: A decimation factor which determines the rate (update_rate_hz/callback_decimation) that
                             the callback function will be called.

        debug_ptr:  Reference to a function which can handle debug messages and do something useful with them.
                    In the wenet payload, we use this to link this object to the PacketTX object to be able to
                    transit debug messages to the ground.

        log_file:   An optional filename in which to log BNO055 state data. Data will be stored as lines of JSON data.
                    Data is written whenever the callback function is called.

        raw_sensor_data:   If set to True, capture all sensor data (i.e. Accelerometer, Gyro, Magnetometer), instead of just
                    the Euler & Quaternion vectors. This results in a read-time performance hit.
        """

        self.port = port
        self.update_rate_hz = update_rate_hz
        self.callback = callback
        self.callback_decimation = callback_decimation
        self.debug_ptr = debug_ptr
        self.raw_sensor_data = raw_sensor_data

        # Open log file, if one has been given.
        if log_file != None:
            self.log_file = open(log_file,'a')
        else:
            self.log_file = None

        self.bno = None

        # Start RX thead.
        self.rx_thread = Thread(target=self.rx_loop)
        self.rx_thread.start()

    def init(self, reset=True):
        while self.bno == None:
            try:
                self.bno = BNO055(serial_port=self.port)
                success = self.bno.begin(reset=reset)
                if success:
                    self.debug_message("Connected to BNO055!")
                    # Set axis remap settings so that UP on the camera image aligns with the heading.
                    # This is specific to the SHSSP2023 payload, and may need to be changed for other payloads.
                    self.bno.set_axis_remap(
                        AXIS_REMAP_Y, 
                        AXIS_REMAP_X, 
                        AXIS_REMAP_Z,
                        x_sign=AXIS_REMAP_NEGATIVE, 
                        y_sign=AXIS_REMAP_POSITIVE,
                        z_sign=AXIS_REMAP_POSITIVE)
                    self.debug_message("Axis remap configured.")
                    continue
                else:
                    self.bno.close()
                    self.bno = None
            except Exception as e:
                self.debug_message("Failed to connect to BNO055: %s" % str(e))
                self.bno = None
            self.debug_message("Attempting BNO055 re-connect in 5 seconds.")
            time.sleep(5)

    def close(self):
        self.rx_running = False
        time.sleep(2)
        self.bno.close()
        if self.log_file != None:
            self.log_file.close()

    def debug_message(self, message):
        """ Write a debug message.
        If debug_ptr was set to a function during init, this will
        pass the message to that function, else it will just print it.
        This is used mainly to get error and other state updates into the Wenet downlink.
        """
        message = "BNO055 Debug: " + message
        if self.debug_ptr != None:
            self.debug_ptr(message)
        else:
            print(message)

    # Lock files for writing and reading to the internal state dictionary.
    state_writelock = False
    state_readlock = False
    state_blockwrite = False

    # Thread-safe read/write access into the internal state dictionary
    def write_state(self, value, parameter, block_write=False):
        """ (Hopefully) thread-safe state dictionary write access """
        while self.state_readlock:
            pass

        self.state_writelock = True
        self.state[value] = parameter
        if not self.state_blockwrite:
            self.state_writelock = False

    def read_state(self):
        """ Thread-safe state dictionary read access. """
        while self.state_writelock:
            pass

        self.state_readlock = True
        state_copy = self.state.copy()
        self.state_readlock = False

        return state_copy

    def bno_callback(self):
        """ Pass the latest state to an external callback function """
        # Grab latest state.
        latest_state = self.read_state()

        # Write into the log file, if we are using one.
        if self.log_file != None:
            self.log_file.write(json.dumps(latest_state) + '\n')

        # If we don't have a callback function to use, return immediately.
        if self.callback == None:
            return
        else:
            self.callback(latest_state)

    rx_running = True
    rx_counter = 0
    def rx_loop(self):
        """ Main BNO055 polling loop. """

        # Initialise BNO055
        self.init()

        while self.rx_running:
            try:
                # Grab a complete set of data from the BNO055
                start_timestamp = time.time()
                start_isotime = datetime.datetime.utcnow().isoformat()
                (heading, roll, pitch) = self.bno.read_euler()
                (quaternion_x, quaternion_y, quaternion_z, quaternion_w) = self.bno.read_quaternion()
                if self.raw_sensor_data:
                    (magnet_x, magnet_y, magnet_z) = self.bno.read_magnetometer()
                    (gyro_x, gyro_y, gyro_z) = self.bno.read_gyroscope()
                    (accel_x, accel_y, accel_z) = self.bno.read_accelerometer()
                    (linear_accel_x, linear_accel_y, linear_accel_z) = self.bno.read_linear_acceleration()
                    (gravity_accel_x, gravity_accel_y, gravity_accel_z) = self.bno.read_gravity()
                (status, self_test, error) = self.bno.get_system_status(run_self_test=False)
                (sys, gyro, accel, mag) = self.bno.get_calibration_status()
                temp = self.bno.read_temp()
                


                # Write into state dictionary as a block, so users can't request a half-updated state dict.
                self.state_blockwrite = True # This locks the state writelock on.

                self.write_state('timestamp', start_timestamp)
                self.write_state('isotime', start_isotime)
                self.write_state('sys_status',status)
                self.write_state('sys_error',error)
                self.write_state('sys_cal', sys)
                self.write_state('gyro_cal', gyro)
                self.write_state('accel_cal', accel)
                self.write_state('magnet_cal', mag)
                self.write_state('temp', temp)
                self.write_state('euler_heading', heading)
                self.write_state('euler_roll', roll)
                self.write_state('euler_pitch', pitch)
                self.write_state('quaternion_x', quaternion_x)
                self.write_state('quaternion_y', quaternion_y)
                self.write_state('quaternion_z', quaternion_z)
                self.write_state('quaternion_w', quaternion_w)
                if self.raw_sensor_data:
                    self.write_state('magnet_x', magnet_x)
                    self.write_state('magnet_y', magnet_y)
                    self.write_state('magnet_z', magnet_z)
                    self.write_state('accel_x', accel_x)
                    self.write_state('accel_y', accel_y)
                    self.write_state('accel_z', accel_z)
                    self.write_state('gyro_x', gyro_x)
                    self.write_state('gyro_y', gyro_y)
                    self.write_state('gyro_z', gyro_z)
                    self.write_state('linear_accel_x', linear_accel_x)
                    self.write_state('linear_accel_y', linear_accel_y)
                    self.write_state('linear_accel_z', linear_accel_z)
                    self.write_state('gravity_accel_x', gravity_accel_x)
                    self.write_state('gravity_accel_y', gravity_accel_y)
                    self.write_state('gravity_accel_z', gravity_accel_z)
                    self.write_state('raw_sensor_data', True)
                self.write_state('valid', True)

                # Clear write locks.
                self.state_blockwrite = False
                self.state_writelock = False

                if self.rx_counter % self.callback_decimation == 0:
                    # Send data to the callback function.
                    callback_thread = Thread(target=self.bno_callback)
                    callback_thread.start()

                self.rx_counter += 1

                # Some logic to store calibration data.
                if (sys==3) and (gyro==3) and (accel==3) and (mag==3) and (self.calibration_data != None):
                    # We are fully calibrated! Suck down this data.
                    self.calibration_data = self.bno.get_calibration()
                    self.debug_message("Calibration Data has been stored.")


            except Exception as e:
                self.debug_message("ERROR: %s" % str(e))
                # Set state validity to false.
                self.write_state('valid', False)
                # Attempt to re-connect.
                self.debug_message("Attempting to re-connect.")
                # Close existing object.
                self.bno.close()
                self.bno = None
                # Attempt to re-connect to BNO055. This will loop until it connects.
                # Don't reset the BNO055 upon reconnection.
                self.init(reset=False)
                # Push in saved calibration data, if we have it.
                if self.calibration_data != None:
                    self.bno.set_calibration(self.calibration_data)
                    self.debug_message("Calibration Data re-loaded.")


            # Delay.
            # NOTE: Currently we don't delay between reads, in an attempt to read as fast as possible.
            #time.sleep(1.0/self.update_rate_hz)

if __name__ == "__main__":
    import sys
    import numpy as np
    port = sys.argv[1]

    last_timestamp = 0
    diffs = []

    def print_state(state):
        global last_timestamp, diffs
        print(state)
        time_diff = state['timestamp']-last_timestamp
        diffs.append(time_diff)
        print(time_diff)
        last_timestamp = state['timestamp']

    imu = WenetBNO055(port=port, update_rate_hz = 5, callback=print_state, callback_decimation=1)

    time.sleep(10)

    imu.close()

    print(diffs)
    print("Average read time: %.5f" % np.mean(diffs[1:]))
















