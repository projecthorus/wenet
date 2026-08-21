# The MIT License (MIT)
#
# Copyright (c) 2016 Radomir Dopieralski (@deshipu),
#               2017 Robert Hammelrath (@robert-hh)
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
#
import time
import struct
import smbus2

_REGISTER_MASK = 0x03
_REGISTER_CONVERT = 0x00
_REGISTER_CONFIG = 0x01
_REGISTER_LOWTHRESH = 0x02
_REGISTER_HITHRESH = 0x03

_OS_MASK = 0x8000
_OS_SINGLE = 0x8000  # Write: Set to start a single-conversion
_OS_BUSY = 0x0000  # Read: Bit=0 when conversion is in progress
_OS_NOTBUSY = 0x8000  # Read: Bit=1 when no conversion is in progress

_MUX_MASK = 0x7000
_MUX_DIFF_0_1 = 0x0000  # Differential P  =  AIN0, N  =  AIN1 (default)
_MUX_DIFF_0_3 = 0x1000  # Differential P  =  AIN0, N  =  AIN3
_MUX_DIFF_1_3 = 0x2000  # Differential P  =  AIN1, N  =  AIN3
_MUX_DIFF_2_3 = 0x3000  # Differential P  =  AIN2, N  =  AIN3
_MUX_SINGLE_0 = 0x4000  # Single-ended AIN0
_MUX_SINGLE_1 = 0x5000  # Single-ended AIN1
_MUX_SINGLE_2 = 0x6000  # Single-ended AIN2
_MUX_SINGLE_3 = 0x7000  # Single-ended AIN3

_PGA_MASK = 0x0E00
_PGA_6_144V = 0x0000  # +/-6.144V range  =  Gain 2/3
_PGA_4_096V = 0x0200  # +/-4.096V range  =  Gain 1
_PGA_2_048V = 0x0400  # +/-2.048V range  =  Gain 2 (default)
_PGA_1_024V = 0x0600  # +/-1.024V range  =  Gain 4
_PGA_0_512V = 0x0800  # +/-0.512V range  =  Gain 8
_PGA_0_256V = 0x0A00  # +/-0.256V range  =  Gain 16

_MODE_MASK = 0x0100
_MODE_CONTIN = 0x0000  # Continuous conversion mode
_MODE_SINGLE = 0x0100  # Power-down single-shot mode (default)

_DR_MASK = 0x00E0     # Values ADS1015/ADS1115
_DR_128SPS = 0x0000   # 128 /8 samples per second
_DR_250SPS = 0x0020   # 250 /16 samples per second
_DR_490SPS = 0x0040   # 490 /32 samples per second
_DR_920SPS = 0x0060   # 920 /64 samples per second
_DR_1600SPS = 0x0080  # 1600/128 samples per second (default)
_DR_2400SPS = 0x00A0  # 2400/250 samples per second
_DR_3300SPS = 0x00C0  # 3300/475 samples per second
_DR_860SPS = 0x00E0   # -   /860 samples per Second

_CMODE_MASK = 0x0010
_CMODE_TRAD = 0x0000    # Traditional comparator with hysteresis (default)
_CMODE_WINDOW = 0x0010  # Window comparator

_CPOL_MASK = 0x0008
_CPOL_ACTVLOW = 0x0000  # ALERT/RDY pin is low when active (default)
_CPOL_ACTVHI = 0x0008   # ALERT/RDY pin is high when active

_CLAT_MASK = 0x0004     # Determines if ALERT/RDY pin latches once asserted
_CLAT_NONLAT = 0x0000   # Non-latching comparator (default)
_CLAT_LATCH = 0x0004    # Latching comparator

_CQUE_MASK = 0x0003
_CQUE_1CONV = 0x0000  # Assert ALERT/RDY after one conversions
_CQUE_2CONV = 0x0001  # Assert ALERT/RDY after two conversions
_CQUE_4CONV = 0x0002  # Assert ALERT/RDY after four conversions
# Disable the comparator and put ALERT/RDY in high state (default)
_CQUE_NONE = 0x0003

_GAINS = (
    _PGA_6_144V,  # 2/3x
    _PGA_4_096V,  # 1x
    _PGA_2_048V,  # 2x
    _PGA_1_024V,  # 4x
    _PGA_0_512V,  # 8x
    _PGA_0_256V   # 16x
)

_GAINS_V = (
    6.144,  # 2/3x
    4.096,  # 1x
    2.048,  # 2x
    1.024,  # 4x
    0.512,  # 8x
    0.256  # 16x
)

_CHANNELS = {
    (0, None): _MUX_SINGLE_0,
    (1, None): _MUX_SINGLE_1,
    (2, None): _MUX_SINGLE_2,
    (3, None): _MUX_SINGLE_3,
    (0, 1): _MUX_DIFF_0_1,
    (0, 3): _MUX_DIFF_0_3,
    (1, 3): _MUX_DIFF_1_3,
    (2, 3): _MUX_DIFF_2_3,
}

_RATES = (
    _DR_128SPS,   # 128/8 samples per second
    _DR_250SPS,   # 250/16 samples per second
    _DR_490SPS,   # 490/32 samples per second
    _DR_920SPS,   # 920/64 samples per second
    _DR_1600SPS,  # 1600/128 samples per second (default)
    _DR_2400SPS,  # 2400/250 samples per second
    _DR_3300SPS,  # 3300/475 samples per second
    _DR_860SPS    # - /860 samples per Second
)


class ADS1115:
    def __init__(self, bus, address=0x48, gain=1):
        self.bus = bus
        self.address = address
        self.gain = gain
        self.temp2 = bytearray(2)

    def _write_register(self, register, value):
        self.temp2[0] = value >> 8
        self.temp2[1] = value & 0xff
        self.bus.write_i2c_block_data(self.address, register, self.temp2)

    def _read_register(self, register):
        self.temp2 = self.bus.read_i2c_block_data(self.address, register, 2)
        return (self.temp2[0] << 8) | self.temp2[1]

    def raw_to_v(self, raw):
        v_p_b = _GAINS_V[self.gain] / 32768
        return raw * v_p_b

    def set_conv(self, rate=4, channel1=0, channel2=None):
        """Set mode for read_rev"""
        self.mode = (_CQUE_NONE | _CLAT_NONLAT |
                     _CPOL_ACTVLOW | _CMODE_TRAD | _RATES[rate] |
                     _MODE_SINGLE | _OS_SINGLE | _GAINS[self.gain] |
                     _CHANNELS[(channel1, channel2)])

    def read(self, rate=4, channel1=0, channel2=None):
        """Read voltage between a channel and GND.
           Time depends on conversion rate."""
        self._write_register(_REGISTER_CONFIG, (_CQUE_NONE | _CLAT_NONLAT |
                             _CPOL_ACTVLOW | _CMODE_TRAD | _RATES[rate] |
                             _MODE_SINGLE | _OS_SINGLE | _GAINS[self.gain] |
                             _CHANNELS[(channel1, channel2)]))
        while not self._read_register(_REGISTER_CONFIG) & _OS_NOTBUSY:
            time.sleep(0.001)
        res = self._read_register(_REGISTER_CONVERT)
        return struct.unpack(">h", res.to_bytes(2, "big"))[0]

    def read_rev(self):
        """Read voltage between a channel and GND. and then start
           the next conversion."""
        res = self._read_register(_REGISTER_CONVERT)
        self._write_register(_REGISTER_CONFIG, self.mode)
        return struct.unpack(">h", res.to_bytes(2, "big"))[0]

    def alert_start(self, rate=4, channel1=0, channel2=None,
                    threshold_high=0x4000, threshold_low=0, latched=False) :
        """Start continuous measurement, set ALERT pin on threshold."""
        self._write_register(_REGISTER_LOWTHRESH, threshold_low)
        self._write_register(_REGISTER_HITHRESH, threshold_high)
        self._write_register(_REGISTER_CONFIG, _CQUE_1CONV |
                             _CLAT_LATCH if latched else _CLAT_NONLAT |
                             _CPOL_ACTVLOW | _CMODE_TRAD | _RATES[rate] |
                             _MODE_CONTIN | _GAINS[self.gain] |
                             _CHANNELS[(channel1, channel2)])

    def conversion_start(self, rate=4, channel1=0, channel2=None):
        """Start continuous measurement, trigger on ALERT/RDY pin."""
        self._write_register(_REGISTER_LOWTHRESH, 0)
        self._write_register(_REGISTER_HITHRESH, 0x8000)
        self._write_register(_REGISTER_CONFIG, _CQUE_1CONV | _CLAT_NONLAT |
                             _CPOL_ACTVLOW | _CMODE_TRAD | _RATES[rate] |
                             _MODE_CONTIN | _GAINS[self.gain] |
                             _CHANNELS[(channel1, channel2)])

    def alert_read(self):
        """Get the last reading from the continuous measurement."""
        res = self._read_register(_REGISTER_CONVERT)
        return struct.unpack(">h", res.to_bytes(2, "big"))[0]


class ADS1113(ADS1115):
    def __init__(self, bus, address=0x48):
        super().__init__(bus, address, 1)

    def raw_to_v(self, raw):
        return super().raw_to_v(raw)

    def read(self, rate=4):
        return super().read(rate, 0, 1)

    def alert_start(self, rate=4, threshold_high=0x4000, threshold_low=0, latched=False):
        return super().alert_start(rate, 0, 1, threshold_high, threshold_low, latched)

    def alert_read(self):
        return super().alert_read()


class ADS1114(ADS1115):
    def __init__(self, bus, address=0x48, gain=1):
        super().__init__(bus, address, gain)

    def raw_to_v(self, raw):
        return super().raw_to_v(raw)

    def read(self, rate=4):
        return super().read(rate, 0, 1)

    def alert_start(self, rate=4, threshold_high=0x4000, threshold_low=0, latched=False):
        return super().alert_start(rate, 0, 1, threshold_high,
            threshold_low, latched)

    def alert_read(self):
        return super().alert_read()


class ADS1015(ADS1115):
    def __init__(self, bus, address=0x48, gain=1):
        super().__init__(bus, address, gain)

    def raw_to_v(self, raw):
        return super().raw_to_v(raw << 4)

    def read(self, rate=4, channel1=0, channel2=None):
        return super().read(rate, channel1, channel2) >> 4

    def alert_start(self, rate=4, channel1=0, channel2=None, threshold_high=0x400,
        threshold_low=0, latched=False):
        return super().alert_start(rate, channel1, channel2, threshold_high << 4,
            threshold_low << 4, latched)

    def alert_read(self):
        return super().alert_read() >> 4