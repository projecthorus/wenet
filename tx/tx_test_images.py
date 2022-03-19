#!/usr/bin/env python
#
#	Test Transmitter Script
#	Transmit a set of images from the test_images directory
#
#	Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#

import PacketTX,  sys, os, argparse

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
parser.add_argument("--baudrate", default=115200, type=int, help="Transmitter baud rate. Defaults to 115200 baud.")
args = parser.parse_args()


tx = PacketTX.PacketTX(debug=debug_output, serial_baud=args.baudrate)
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
