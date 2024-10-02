#!/usr/bin/env python
#
#	Test Transmitter Script
#	Transmit a set of images from the test_images directory
#
#	Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#

import PacketTX,  sys, os, argparse, logging
from radio_wrappers import *

# Set to whatever resolution you want to test.
file_path = "../test_images/%d_raw.bin" # _raw, _800x608, _640x480, _320x240
image_numbers = range(1,14)

debug_output = False # If True, packet bits are saved to debug.bin as one char per bit.

def transmit_file(filename, tx_object):
	file_size = os.path.getsize(filename)

	if file_size % 256 > 0:
		print("File size not a multiple of 256 bytes!")
		return

	print("Transmitting %d Packets." % (file_size//256))

	f = open(filename,'rb')

	for x in range(file_size//256):
		data = f.read(256)
		tx_object.tx_packet(data)

	f.close()
	print("Waiting for tx queue to empty...")
	tx_object.wait()




parser = argparse.ArgumentParser()
parser.add_argument("--rfm98w", default=None, type=int, help="If set, configure a RFM98W on this SPI device number.")
parser.add_argument("--frequency", default=443.500, type=float, help="Transmit Frequency (MHz). (Default: 443.500 MHz)")
parser.add_argument("--baudrate", default=115200, type=int, help="Wenet TX baud rate. (Default: 115200).")
parser.add_argument("--serial_port", default="/dev/ttyAMA0", type=str, help="Serial Port for modulation.")
parser.add_argument("--tx_power", default=17, type=int, help="Transmit power in dBm (Default: 17 dBm, 50mW. Allowed values: 2-17)")
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

tx = PacketTX.PacketTX(
	radio=radio,
	udp_listener=55674)

tx.start_tx()

print("TX Started. Press Ctrl-C to stop.")
try:
	for img in image_numbers:
		filename = file_path % img
		print("\nTXing: %s" % filename)
		transmit_file(filename,tx)
	tx.close()
except KeyboardInterrupt:
	print("Closing...")
	tx.close()
