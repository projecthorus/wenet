#!/usr/bin/env python
#
#	Wenet - SHSSP Payload Main Loop - 2023 Version
#
#	Copyright (C) 2023  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#	
#	Requires:
#		- PiCamera
#		- uBlox GPS Unit, available at /dev/ublox
#		- Bosch BNO055 Absolute Orientation Sensor, available at /dev/bno
#		- Wenet TX Shield, available on /dev/ttyAMA0
#


import PacketTX
import WenetPiCam
import ublox
import json
import argparse
import time
import traceback
import datetime
import os
import subprocess
from BNO055 import WenetBNO055
from threading import Thread

def get_cpu_temperature():
    """ Grab the temperature of the RPi CPU """
    try:
        data = subprocess.check_output("/usr/bin/vcgencmd measure_temp", shell=True)
        temp = data.decode().split('=')[1].split('\'')[0]
        return float(temp)
    except Exception as e:
        print("Error reading temperature - %s" % str(e))
        return -999

def get_cpu_speed():
	""" Get the current CPU Frequency """
	try:
		data = subprocess.check_output("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", shell=True)
		freq = int(data.decode().strip())/1000
		return freq
	except Exception as e:
		print("Error reading CPU Freq - %s" % str(e))
		return -1


# Payload Callsigns
global_callsign = "VK5QI"
#global_callsign = "SHSSP1"

# Image capture directory
image_dir = "./tx_images/"

# Log files.
text_telemetry_log = "ssp1_text.log"
imu_log = "ssp1_imu.log"
gps_log = "ssp1_gps.log"

# Start up Wenet TX Object.
tx = PacketTX.PacketTX(serial_port='/dev/ttyAMA0', 
					serial_baud=115200, 
					callsign=global_callsign,
					log_file=text_telemetry_log)
tx.start_tx()

# Sleep for a second to let the transmitter fire up.
time.sleep(1)


# Initialize BNO055 Connection.
# The main thread within this class will continually try and
# connect to a BNO055. We can still request data from it during this
# however it will just return zeros.
bno = WenetBNO055(port='/dev/bno',
	update_rate_hz = 5,  # Note that this parameter is un-used now.
	callback_decimation = 1, # Save IMU data to disk at full rate (~ 10 Hz for just euler/quaternion data)
	debug_ptr = tx.transmit_text_message, 
	log_file=imu_log,
	raw_sensor_data = False)


# Global variable to record if the GPS is giving valid time data.
# As the GPS can go back to a fix state of 0, yet still give valid time data (for our purposes anyway),
# We latch this variable to True as soon as we see any valid fix state.
gps_time_fix = False

# Global variable to tell if we've set the system time to GPS.
# We need to set the system time at least once manually (using timedatectl), before NTPD can take over.
system_time_set = False

def handle_gps_data(gps_data):
	""" Handle GPS data passed to us from a UBloxGPS instance """
	global tx, bno, gps_time_fix, system_time_set

	# Latch gps_time_fix if Fix is OK.
	if gps_data['gpsFix'] > 0:
		gps_time_fix = True

	# Grab a snapshot of orientation data.
	orientation_data = bno.read_state()

	# If we have GPS lock, set the system clock to it. (Only do this once.)
	if (gps_data['gpsFix'] == 3) and not system_time_set:
		dt = gps_data['datetime']
		try:
			new_time = dt.strftime('%Y-%m-%d %H:%M:%S')
			ret_code = os.system("timedatectl set-time \"%s\"" % new_time)
			if ret_code == 0:
				tx.transmit_text_message("GPS Debug: System clock set to GPS time %s" % new_time)
			else:
				tx.transmit_text_message("GPS Debug: Attempt to set system clock failed!")
			system_time_set = True
		except:
			tx.transmit_text_message("GPS Debug: Attempt to set system clock failed!")

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
		log_file = gps_log,
		ntpd_update = True
		)
except Exception as e:
	tx.transmit_text_message("ERROR: Could not Open GPS - %s" % str(e), repeats=5)
	gps = None

# Initialise the Camera Objects.

# Initialise PiCam, using default capture and transmit resolution.
while True:
	try:
		picam = WenetPiCam.WenetPiCam(callsign=global_callsign, 
			src_resolution=(3280,2464), 
			tx_resolution=(1488,1120),
			num_images=1, 	# Only capture one image at a time.
			debug_ptr=tx.transmit_text_message, 
			vertical_flip=True, 
			horizontal_flip=True,
			greyworld=True)
		
		# If this succeeded, break out of this loop.
		break
	except Exception as e:
		tx.transmit_text_message("Error initialising Picamera - %s" % str(e))
		time.sleep(2)
		# Continue looping to ensure the error message continues to be sent...

# SSDV Image ID.
image_id = 0

# Main 'loop'.
while True:
	try:
		# Grab current timestamp for image filenames.
		gps_data = gps.read_state()
		if gps_time_fix:
			# The timestamp supplied within the gps data dictionary isn't suitable for use as a filename.
			# Do the conversion from week/iTOW/leapS to UTC time manually, and produce a suitable timestamp.
			epoch = datetime.datetime.strptime("1980-01-06 00:00:00","%Y-%m-%d %H:%M:%S")
			elapsed = datetime.timedelta(days=(gps_data['week']*7),seconds=(gps_data['iTOW']))
			timestamp = epoch + elapsed - datetime.timedelta(seconds=gps_data['leapS'])
			capture_time = timestamp.strftime("%Y%m%d-%H%M%SZ")
		else:
			# If we don't have valid GPS time, use system time. 
			capture_time = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%SZ")

		# Generate output filenames.
		vis_capture_filename = image_dir + "/%s_%d_ir.jpg" % (capture_time,image_id)
		metadata_filename = image_dir + "/%s_%d_metadata.json" % (capture_time, image_id)

		# Capture an instantaneous snapshot of GPS and Orientation data.
		print(f"Gathering GPS & IMU Data: {time.time()}")
		gps_data = gps.read_state()
		orientation_data = bno.read_state()

		# Capture picam image.
		picam_capture_success = picam.capture(vis_capture_filename)

		# If we have images, convert to SSDV.
		if picam_capture_success:
			# Transmit a summary of what images we were able to capture.
			tx.transmit_text_message("Image %d Captured at %s (%s)" % (
				image_id, 
				capture_time,
				"GPS" if gps_time_fix else "System")
			)

			# Convert image to SSDV
			picam_ssdv_filename = picam.ssdvify(vis_capture_filename, image_id = image_id)
		
		else:
			time.sleep(2)
			tx.transmit_text_message("Capture failed! Attempting to reset camera...")

			try:
				picam.cam.close()
			except:
				tx.transmit_text_message("Closing camera object failed.")

			try:
				picam.init_camera()
			except Exception as e:
				tx.transmit_text_message("Error initializing camera - %s" % str(e))
				time.sleep(1)

			# Go back to the start of the loop and try again...
			continue

		if picam_ssdv_filename == "FAIL":
			tx.transmit_text_message("Error capturing image, continuing.")
			continue

		# Wait until the transmit queue is empty before pushing in packets.
		tx.transmit_text_message("Waiting for SSDV TX queue to empty.")
		while tx.image_queue_empty() == False:
			time.sleep(0.1) # Sleep for a short amount of time.

		if picam_capture_success:
			# Get file size in packets.
			file_size = os.path.getsize(picam_ssdv_filename)/256

			tx.transmit_text_message("Transmitting %d SSDV Packets." % file_size)

			tx.queue_image_file(picam_ssdv_filename)

		# Transmit Image telemetry packet
		tx.transmit_image_telemetry(gps_data, orientation_data, image_id, callsign=global_callsign)

		# Dump all the image metadata to a json blob, and write to a file.
		gps_data.pop('datetime') # Pop out the datetime object, as it isn't serialisable. We still have the timestamp entry...
		metadata = {'gps': gps_data, 'orientation': orientation_data, 'image_id': image_id}
		f = open(metadata_filename,'w')
		f.write(json.dumps(metadata))
		f.close()

		# Increment image ID and loop!
		image_id = (image_id + 1) % 256

		_cpu_temp = get_cpu_temperature()
		_cpu_freq = get_cpu_speed()
		tx.transmit_text_message(f"CPU State: Temperature: {_cpu_temp:.1f} degC, Frequency: {_cpu_freq} MHz")

	# Catch CTRL-C, and exit cleanly.
	# Only really used during debugging.
	except KeyboardInterrupt:
		print("Closing")
		bno.close()
		gps.close()
		picam.stop()
		tx.close()
		break

	except Exception as e:
		tx.transmit_text_message("Exception in main loop: %s" % str(e))
		time.sleep(0.5)

















