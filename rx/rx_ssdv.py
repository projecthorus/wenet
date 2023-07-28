#!/usr/bin/env python
#
#	SSDV Packet Receiver & Parser
#	Decodes SSDV packets passed via stdin.
#
#	Copyright (C) 2022  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#
#	Requires: ssdv (https://github.com/fsphil/ssdv)
#

import codecs
import datetime
import json
import logging
import os
import os.path
import sys
import datetime
import argparse
import socket
import traceback
from WenetPackets import *



parser = argparse.ArgumentParser()
parser.add_argument("--hex", action="store_true", help="Take Hex strings as input instead of raw data.")
parser.add_argument("--partialupdate", default=0, help="Push partial updates every N packets to GUI.")
parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Verbose output")
parser.add_argument("--headless", action='store_true', default=False, help="Headless mode - broadcasts additional data via UDP.")
parser.add_argument("--rximages", default="./rx_images/", help="Location to save RX images and telemetry to.")
args = parser.parse_args()

RX_IMAGES_DIR = args.rximages

# Set up log output.
if args.verbose:
	log_level = logging.DEBUG
else:
	log_level = logging.INFO

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


LOG_FILENAME = os.path.join(args.rximages,datetime.datetime.utcnow().strftime("%Y%m%d-%H%MZ"))


# GUI updates are only sent locally.
def trigger_gui_update(filename, text = "None", metadata = None):
	message = 	{'filename': filename,
				'text': text,
				'metadata': metadata}

	gui_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	gui_socket.sendto(json.dumps(message).encode('ascii'),("127.0.0.1",WENET_IMAGE_UDP_PORT))
	gui_socket.close()


# Telemetry packets are send via UDP broadcast in case there is other software on the local
# network that wants them.
def broadcast_telemetry_packet(data, headless=False):
	telemetry_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	# Set up the telemetry socket so it can be re-used.
	telemetry_socket.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
	telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	# We need the following if running on OSX.
	try:
		telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
	except:
		pass

	# Place data into dictionary.
	data = {'type': 'WENET', 'packet': list(bytearray(data))}

	# Send to broadcast if we can.
	try:
		telemetry_socket.sendto(json.dumps(data).encode('ascii'), ('<broadcast>', WENET_TELEMETRY_UDP_PORT))
	except socket.error:
		telemetry_socket.sendto(json.dumps(data).encode('ascii'), ('127.0.0.1', WENET_TELEMETRY_UDP_PORT))

	telemetry_socket.close()


	if headless:
		# In headless mode, we also send the above data via the image port.
		gui_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		gui_socket.sendto(json.dumps(data).encode('ascii'),("127.0.0.1",WENET_IMAGE_UDP_PORT))
		gui_socket.close()


def log_telemetry_packet(packet):
	global START_DATETIME

	packet_type = decode_packet_type(packet)

	if packet_type == WENET_PACKET_TYPES.IDLE:
		return

	elif packet_type == WENET_PACKET_TYPES.TEXT_MESSAGE:
		decoded = decode_text_message(packet)

		_log_f = open(LOG_FILENAME+"_text.log",'a')
		_log_f.write(json.dumps(decoded)+"\n")
		_log_f.close()

	elif packet_type == WENET_PACKET_TYPES.SEC_PAYLOAD_TELEMETRY:
		decoded = sec_payload_decode(packet)
		# Convert payload (bytes) into a hexadecimal string so we can serialise it.
		decoded['payload'] = codecs.encode(decoded['payload'],'hex').decode()

		_log_f = open(LOG_FILENAME+"_secondary.log",'a')
		_log_f.write(json.dumps(decoded)+"\n")
		_log_f.close()

	elif packet_type == WENET_PACKET_TYPES.GPS_TELEMETRY:
		decoded = gps_telemetry_decoder(packet)

		_log_f = open(LOG_FILENAME+"_gps.log",'a')
		_log_f.write(json.dumps(decoded)+"\n")
		_log_f.close()

	elif packet_type == WENET_PACKET_TYPES.ORIENTATION_TELEMETRY:
		decoded = orientation_telemetry_decoder(packet)

		_log_f = open(LOG_FILENAME+"_orientation.log",'a')
		_log_f.write(json.dumps(decoded)+"\n")
		_log_f.close()

	elif packet_type == WENET_PACKET_TYPES.IMAGE_TELEMETRY:
		decoded = image_telemetry_decoder(packet)

		_log_f = open(LOG_FILENAME+"_imagetelem.log",'a')
		_log_f.write(json.dumps(decoded)+"\n")
		_log_f.close()




# State variables
current_image = -1
current_callsign = ""
current_text_message = -1
current_packet_count = 0
current_packet_time = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%SZ")

# Open temporary file for storing data.
temp_f = open("rxtemp.bin",'wb')


while True:
	if args.hex:
		# Incoming data is as a hexadecimal string.
		# We can read these in safely using sys.stdin.readline(), 
		# and then pass them into codecs.decode to obtain either a
		# str (Python 2), or bytes (python 3)
		data = sys.stdin.readline().rstrip()
		data = codecs.decode(data, 'hex')
	else:
		# If we are receiving raw binary data via stdin, we need
		# to use the buffer interface under Python 3.
		data = sys.stdin.buffer.read(256)

		# if data == '':
		# 	logging.critical("Caught EOF. Exiting.")
		# 	sys.exit(1)


	if data == b'':
		# EOF! Quit.
		logging.critical("EOF on stdin, possible rtl_sdr failure? Exiting.")
		sys.exit(1)

	try:
		packet_type = decode_packet_type(data)

		if packet_type == WENET_PACKET_TYPES.IDLE:
			continue
		elif packet_type == WENET_PACKET_TYPES.TEXT_MESSAGE:
			broadcast_telemetry_packet(data, args.headless)
			logging.info(packet_to_string(data))
			log_telemetry_packet(data)

		elif packet_type == WENET_PACKET_TYPES.SEC_PAYLOAD_TELEMETRY:
			broadcast_telemetry_packet(data)
			logging.info(packet_to_string(data))
			log_telemetry_packet(data)

		elif packet_type == WENET_PACKET_TYPES.GPS_TELEMETRY:
			broadcast_telemetry_packet(data, args.headless)
			logging.info(packet_to_string(data))
			log_telemetry_packet(data)

		elif packet_type == WENET_PACKET_TYPES.ORIENTATION_TELEMETRY:
			broadcast_telemetry_packet(data, args.headless)
			logging.info(packet_to_string(data))
			log_telemetry_packet(data)

		elif packet_type == WENET_PACKET_TYPES.IMAGE_TELEMETRY:
			broadcast_telemetry_packet(data, args.headless)
			logging.info(packet_to_string(data))
			log_telemetry_packet(data)

		elif packet_type == WENET_PACKET_TYPES.SSDV:

			# Extract packet information.
			packet_info = ssdv_packet_info(data)
			packet_as_string = ssdv_packet_string(data)

			# Only proceed if there are no decode errors.
			if packet_info['error'] != 'None':
				logging.error(message['error'])
				continue

			if (packet_info['image_id'] != current_image) or (packet_info['callsign'] != current_callsign) :
				# Attempt to decode current image if we have enough packets.
				logging.info("New image - ID #%d" % packet_info['image_id'])
				if current_packet_count > 0:
					# Attempt to decode current image, and write out to a file.
					temp_f.close()
					# Run SSDV
					_dessdv_filename = os.path.join(RX_IMAGES_DIR,f"{current_packet_time}_{current_callsign}_{current_image}")
					returncode = os.system(f"ssdv -d rxtemp.bin {_dessdv_filename}.jpg 2>/dev/null > /dev/null")
					if returncode == 1:
						logging.error("ERROR: SSDV Decode failed!")
					else:
						logging.debug("SSDV Decoded OK!")
						# Make a copy of the raw binary data.
						os.system(f"mv rxtemp.bin {_dessdv_filename}.bin")

						# Update live displays here.
						trigger_gui_update(os.path.abspath(_dessdv_filename+".jpg"), packet_as_string, packet_info)

						# Trigger upload to habhub here.
				else:
					logging.debug("Not enough packets to decode previous image.")

				# Now set up for the new image.
				current_image = packet_info['image_id']
				current_callsign = packet_info['callsign']
				current_packet_count = 1
				current_packet_time = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%SZ")
				# Open file and write in first packet.
				temp_f = open("rxtemp.bin" , "wb")
				temp_f.write(data)

			else:
				# Write current packet into temp file.
				temp_f.write(data)
				current_packet_count += 1

				if args.partialupdate != 0:
					if current_packet_count % int(args.partialupdate) == 0:
						# Run the SSDV decoder and push a partial update to the GUI.
						temp_f.flush()
						returncode = os.system("ssdv -d rxtemp.bin rxtemp.jpg 2>/dev/null > /dev/null")
						if returncode == 0:
							logging.debug("Wrote out partial update of image ID #%d" % current_image)
							trigger_gui_update(os.path.abspath("rxtemp.jpg"), packet_as_string, packet_info)
		else:
			logging.debug("Unknown Packet Format.")
	
	except Exception as e:
		logging.error("Error handling packet - " + str(e))