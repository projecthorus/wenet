#!/usr/bin/env python
#
#	SHSSP Payload Main Loop
#	
#	Requires:
#		- PiCamera + NIR Filter
#		- Logitech C920 Webcam (or equivalent, with changes to the WenetFSWebcam call below)
#		- uBlox GPS Unit, available at /dev/ublox
#		- Bosch BNO055 Absolute Orientation Sensor, available at /dev/bno
#		- Wenet TX Shield, available on /dev/ttyAMA0
#
#	Mark Jessop <vk5qi@rfhead.net>
#

import PacketTX
import WenetPiCam
import WenetFSWebcam
import ublox
import json
import argparse
import time
import traceback
import datetime
import os
from BNO055 import WenetBNO055
from threading import Thread

# Payload Callsigns
global_callsign = "SHSSP1"
vis_callsign = "SSP1VI"
nir_callsign = "SSP1IR"

# Image capture directory
image_dir = "./tx_images/"

# Log files.
text_telemetry_log = "ssp1_text.log"
bno_log = "ssp1_bno.log"
gps_log = "ssp1_gps.log"

# Start up Wenet TX Object.
tx = PacketTX.PacketTX(serial_port='/dev/ttyAMA0', serial_baud=115200, callsign=vis_callsign)
tx.start_tx()

# Sleep for a second to let the transmitter fire up.
time.sleep(1)


# Initiaise BNO055.
# This will loop until it has connected to a BNO055.
bno = WenetBNO055(port='/dev/bno',
	update_rate_hz = 5, 
	debug_ptr = tx.transmit_text_message, 
	log_file=bno_log)

# Global variable to record if the GPS is giving valid time data.
# As the GPS can go back to a fix state of 0, yet still give valid time data (for our purposes anyway),
# We latch this variable to True as soon as we see any valid fix state.
gps_time_fix = False

def handle_gps_data(gps_data):
	""" Handle GPS data passed to us from a UBloxGPS instance """
	global tx, bno, gps_time_fix

	# Latch gps_time_fix if Fix is OK.
	if gps_data['gpsFix'] > 0:
		gps_time_fix = True

	# Grab a snapshot of orientation data.
	orientation_data = bno.read_state()

	# Immediately generate and transmit a GPS packet.
	tx.transmit_gps_telemetry(gps_data)

	# Now transmit an orientation telemetry packet.
	tx.transmit_orientation_telemetry(gps_data['week'], gps_data['iTOW'], gps_data['leapS'], orientation_data)


# Try and start up the GPS rx thread.
# Note: The UBloxGPS constructor will continuously loop until it finds a GPS unit to connect to.
try:
	gps = ublox.UBloxGPS(port='/dev/ublox', 
		dynamic_model = ublox.DYNAMIC_MODEL_AIRBORNE1G, 
		update_rate_ms = 1000,
		debug_ptr = tx.transmit_text_message,
		callback = handle_gps_data,
		log_file = gps_log
		)
except Exception as e:
	tx.transmit_text_message("ERROR: Could not Open GPS - %s" % str(e), repeats=5)
	gps = None

# Initialise the Camera Objects.

# Initialise PiCam, using default capture and transmit resolution.
picam = WenetPiCam.WenetPiCam(callsign=nir_callsign, 
	num_images=1, 	# Only capture one image at a time.
	debug_ptr=tx.transmit_text_message, 
	vertical_flip=False, 
	horizontal_flip=False)

# Initialise Webcam object, again using default resolution settings.
webcam = WenetFSWebcam.WenetFSWebcam(callsign=vis_callsign,
	num_images = 1,
	debug_ptr=tx.transmit_text_message,
	)

# SSDV Image ID.
image_id = 0

# The Webcam capture function takes longer than the picam capture function, so we need to
# insert a brief delay between starting the webcam capture, and capturing from the picam.
webcam_delay = 2.0 # seconds. To be tuned.

# Main 'loop'.
try:
	while True:
		# Grab current timestamp for image filenames.
		gps_data = gps.read_state()
		if gps_time_fix:
			# The timestamp supplied within the gps data dictionary isn't suitable for use as a filename.
			# Do the conversion from week/iTOW/leapS to UTC time manually, and produce a suitable timestamp.
			epoch = datetime.datetime.strptime("1980-01-06 00:00:00","%Y-%m-%d %H:%M:%S")
			elapsed = datetime.timedelta(days=(gps_data['week']*7),seconds=(gps_data['iTOW']+gps_data['leapS']))
			timestamp = epoch + elapsed
			capture_time = timestamp.strftime("%Y%m%d-%H%M%SZ")
		else:
			# If we don't have valid GPS time, use system time. 
			capture_time = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%SZ")

		# Generate output filenames.
		vis_capture_filename = image_dir + "/%s_%d_visible.jpg" % (capture_time,image_id)
		nir_capture_filename = image_dir + "/%s_%d_nir.jpg" % (capture_time, image_id)
		metadata_filename = image_dir + "/%s_%d_metadata.json" % (capture_time, image_id)

		# Fire off webcam capture in a thread.
		webcam_capture = Thread(target=webcam.capture, kwargs=dict(
			filename=vis_capture_filename))
		webcam_capture.start()

		# Sleep before capturing from the picam.
		time.sleep(webcam_delay)

		# Capture an instantaneous snapshot of GPS and Orientation data.
		gps_data = gps.read_state()
		orientation_data = bno.read_state()

		# Capture picam image.
		picam_capture_success = picam.capture(nir_capture_filename)

		# Wait for Webcam capture to complete.
		webcam_capture.join()

		# Check if the webcam has actually captured an image.
		webcam_capture_success = os.path.isfile(vis_capture_filename)

		# Transmit a summary of what images we were able to capture.
		tx.transmit_text_message("Image %d Captured at %s (%s): VIS = %s, NIR = %s" % (
			image_id, 
			capture_time,
			"GPS" if gps_time_fix else "System",
			str(webcam_capture_success), 
			str(picam_capture_success)))

		# If we have images, convert to SSDV.
		if picam_capture_success:
			picam_ssdv_filename = picam.ssdvify(nir_capture_filename, image_id = image_id)

		if webcam_capture_success:
			webcam_ssdv_filename = webcam.ssdvify(vis_capture_filename, image_id = image_id)

		# Wait until the transmit queue is empty before pushing in packets.
		tx.transmit_text_message("Waiting for SSDV TX queue to empty.")
		while tx.image_queue_empty() == False:
			time.sleep(0.1) # Sleep for a short amount of time.

		if picam_capture_success:
			# Get file size in packets.
			file_size = os.path.getsize(picam_ssdv_filename)/256

			tx.transmit_text_message("Transmitting %d NIR SSDV Packets." % file_size)

			tx.queue_image_file(picam_ssdv_filename)

		# Wait until the transmit queue is empty before pushing in packets.
		tx.transmit_text_message("Waiting for SSDV TX queue to empty.")
		while tx.image_queue_empty() == False:
			time.sleep(0.1) # Sleep for a short amount of time.

		if webcam_capture_success:
			# Get file size in packets.
			file_size = os.path.getsize(webcam_ssdv_filename)/256

			tx.transmit_text_message("Transmitting %d Visible SSDV Packets." % file_size)

			tx.queue_image_file(webcam_ssdv_filename)

		# Transmit Image telemetry packet
		tx.transmit_image_telemetry(gps_data, orientation_data, image_id, callsign=global_callsign)

		# Dump all the image metadata to a json blob, and write to a file.
		metadata = {'gps': gps_data, 'orientation': orientation_data, 'image_id': image_id}
		f = open(metadata_filename,'w')
		f.write(json.dumps(metadata))
		f.close()

		# Increment image ID and loop!
		image_id = (image_id + 1) % 256


# Catch CTRL-C, and exit cleanly.
# Only really used during debugging.
except KeyboardInterrupt:
	print("Closing")
	bno.close()
	gps.close()
	picam.stop()
	tx.close()

















