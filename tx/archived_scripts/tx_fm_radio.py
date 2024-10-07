#!/usr/bin/env python
#
#	Proof-of-concept code to transmit Wenet FSK using a FM rig with a 9600 baud input.
#	Currently just transmits example images.
#
#	Notes:
#	I used a 5V FTDI USB-TTL adaptor, and an Icom IC-7000
#	DTR was wired directly to the PTT line on the 6-pin mini-DIN connector.
#	DTR Active (Low) = PTT enabled.
#	The TXD line was dropped in level using a 1k 10-turn potentiometer, and fed
#	into the DATA IN line on the 6-pin mini-DIN. The 10-turn pot was set so the 
#	output Vp-p is about 0.3V, though I then did more adjustment looking at the
#	spectrum of the generated signal.
#	
#	This method of producing FSK is pretty nasty, and probably isn't recommended
#	for serious use.
#
#	Copyright (C) 2019  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#

import PacketTX,  sys, os, argparse

# Set to whatever resolution you want to test.
file_path = "../test_images/%d_320x240.ssdv" # _raw, _800x608, _640x480, _320x240
image_numbers = xrange(1,14)

debug_output = False # If True, packet bits are saved to debug.bin as one char per bit.

def transmit_file(filename, tx_object):
	file_size = os.path.getsize(filename)

	if file_size % 256 > 0:
		print("File size not a multiple of 256 bytes!")
		return

	print("Transmitting %d Packets." % (file_size/256))

	f = open(filename,'rb')

	for x in range(file_size/256):
		data = f.read(256)
		tx_object.tx_packet(data)

	f.close()
	print("Waiting for tx queue to empty...")
	tx_object.wait()


parser = argparse.ArgumentParser()
parser.add_argument("--port", default='/dev/ttyUSB0', type=str, help="Serial port to use for transmit.")
parser.add_argument("--baudrate", default=4800, type=int, help="Transmitter baud rate. Defaults to 4800 baud.")
args = parser.parse_args()


tx = PacketTX.PacketTX(debug=debug_output, serial_port=args.port, serial_baud=args.baudrate)

# Start the transmit thread
tx.start_tx()

# Enable the PTT
tx.s.dtr = True
print("PTT ON!")

print("TX Started. Press Ctrl-C to stop.")
try:
	for img in image_numbers:
		filename = file_path % img
		print("\nTXing: %s" % filename)
		transmit_file(filename,tx)
	tx.close()
except KeyboardInterrupt:
	print("Closing...")

	# Disable the PTT
	tx.s.dtr = False
	print("PTT Off")

	tx.close()
