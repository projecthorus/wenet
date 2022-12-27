#!/usr/bin/env python2.7
#
#	Wenet PiCam Wrapper Class.
#
#	Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#
#	PiCamera API: https://picamera.readthedocs.io/en/release-1.12/api_camera.html

import picamera
from picamera import mmal 
import ctypes as ct
from time import sleep
from threading import Thread
import glob
import os
import datetime
import time
import traceback


class PiCamera2(picamera.PiCamera):
    AWB_MODES = {
        'off':           mmal.MMAL_PARAM_AWBMODE_OFF,
        'auto':          mmal.MMAL_PARAM_AWBMODE_AUTO,
        'sunlight':      mmal.MMAL_PARAM_AWBMODE_SUNLIGHT,
        'cloudy':        mmal.MMAL_PARAM_AWBMODE_CLOUDY,
        'shade':         mmal.MMAL_PARAM_AWBMODE_SHADE,
        'tungsten':      mmal.MMAL_PARAM_AWBMODE_TUNGSTEN,
        'fluorescent':   mmal.MMAL_PARAM_AWBMODE_FLUORESCENT,
        'incandescent':  mmal.MMAL_PARAM_AWBMODE_INCANDESCENT,
        'flash':         mmal.MMAL_PARAM_AWBMODE_FLASH,
        'horizon':       mmal.MMAL_PARAM_AWBMODE_HORIZON,
        'greyworld':     ct.c_uint32(10)
        }


class WenetPiCam(object):
	""" PiCam Wrapper Class

	PiCam Image Source for Wenet.
	Captures multiple images, picks the best, then 
	transmits it via a PacketTX object. 


	"""

	def __init__(self,
				callsign = "N0CALL",
				src_resolution=(3280,2464),
				tx_resolution=(1488,1120), 
				num_images=1,
				image_delay=0.5, 
				vertical_flip = False, 
				horizontal_flip = False,
				greyworld = False,
				temp_filename_prefix = 'picam_temp',
				debug_ptr = None
				):

		""" Instantiate a WenetPiCam Object
			used to capture images from a PiCam using 'optimal' capture techniques.

			Keyword Arguments:
			callsign: The callsign to be used when converting images to SSDV. Must be <=6 characters in length.
			src_resolution: Raw image capture resolution. This is the resolution of the file saved to disk.
			tx_resolution: Tuple (x,y) containing desired image *transmit* resolution.
						NOTE: both x and y need to be multiples of 16 to be used with SSDV.
						NOTE: This will resize with NO REGARD FOR ASPECT RATIO - it's up to you to get that right.

			num_images: Number of images to capture in sequence when the 'capture' function is called.
						The 'best' (largest filesize) image is selected and saved.
			image_delay: Delay time (seconds) between each captured image.

			vertical_flip: Flip captured images vertically.
			horizontal_flip: Flip captured images horizontally.
							Used to correct for picam orientation.

			temp_filename_prefix: prefix used for temporary files.

			debug_ptr:	'pointer' to a function which can handle debug messages.
						This function needs to be able to accept a string.
						Used to get status messages into the downlink.

		"""

		self.debug_ptr = debug_ptr
		self.temp_filename_prefix = temp_filename_prefix
		self.num_images = num_images
		self.image_delay = image_delay
		self.callsign = callsign
		self.tx_resolution = tx_resolution
		self.src_resolution = src_resolution
		self.horizontal_flip = horizontal_flip
		self.vertical_flip = vertical_flip
		self.greyworld = greyworld

		self.init_camera()


	def init_camera(self):
		# Attempt to start picam.
		self.cam = PiCamera2()

		# Configure camera.
		try:
			self.cam.resolution = self.src_resolution
		except:
			# Default to Picam 1 max resolution if we cannot set the higher PiCam 2 resolution.
			self.cam.resolution = (2592,1944)
		self.cam.hflip = self.horizontal_flip
		self.cam.vflip = self.vertical_flip
		self.cam.exposure_mode = 'auto'
		if self.greyworld:
			self.cam.awb_mode = 'greyworld' # 'Greyworld' white balance, for NIR imagery.
		else:
			self.cam.awb_mode = 'sunlight' # Fixed white balance compensation. 
		self.cam.meter_mode = 'matrix'

		# Start the 'preview' mode, effectively opening the 'shutter'.
		# This lets the camera gain control algs start to settle.
		self.cam.start_preview()

	def debug_message(self, message):
		""" Write a debug message.
		If debug_ptr was set to a function during init, this will
		pass the message to that function, else it will just print it.
		This is used mainly to get updates on image capture into the Wenet downlink.

		"""
		message = "PiCam Debug: " + message
		if self.debug_ptr != None:
			self.debug_ptr(message)
		else:
			print(message)

	def close(self):
		self.cam.close()

	def capture(self, filename='picam.jpg', quality=90, bayer=False):
		""" Capture an image using the PiCam
			
			Keyword Arguments:
			filename:	destination filename.
		"""

		# Attempt to capture a set of images.
		for i in range(self.num_images):
			self.debug_message("Capturing Image %d of %d" % (i+1,self.num_images))
			# Wrap this in error handling in case we lose the camera for some reason.
			try:
				self.cam.capture("%s_%d.jpg" % (self.temp_filename_prefix,i), quality=quality, bayer=bayer)
				print(f"Image captured: {time.time()}")
				if self.image_delay > 0:
					sleep(self.image_delay)
			except Exception as e: # TODO: Narrow this down...
				self.debug_message("Capture Error: %s" % str(e))
				# Immediately return false. Not much point continuing to try and capture images.
				return False

		
		# Otherwise, continue to pick the 'best' image based on filesize.
		self.debug_message("Choosing Best Image.")
		pic_list = glob.glob("%s_*.jpg" % self.temp_filename_prefix)
		pic_sizes = []
		# Iterate through list of images and get the file sizes.
		for pic in pic_list:
			pic_sizes.append(os.path.getsize(pic))
		largest_pic = pic_list[pic_sizes.index(max(pic_sizes))]

		# Copy best image to target filename.
		self.debug_message("Copying image to storage with filename %s" % filename)
		os.system("cp %s %s" % (largest_pic, filename))
		# Clean up temporary images.
		os.system("rm %s_*.jpg" % self.temp_filename_prefix)

		return True 

	def ssdvify(self, filename="output.jpg", image_id=0, quality=6):
		""" Convert a supplied JPEG image to SSDV.
		Returns the filename of the converted SSDV image.

		Keyword Arguments:
		filename:	Source JPEG filename.
					Output SSDV image will be saved to to a temporary file (webcam_temp.jpg) which should be
					transmitted immediately.
		image_id:	Image ID number. Must be incremented between images.
		quality:	JPEG quality level: 4 - 7, where 7 is 'lossless' (not recommended).
					6 provides good quality at decent file-sizes.

		"""

		# Wrap image ID field if it's >255.
		image_id = image_id % 256

		# Resize image to the desired resolution.
		self.debug_message("Resizing image.")
		return_code = os.system("convert %s -resize %dx%d\! picam_temp.jpg" % (filename, self.tx_resolution[0], self.tx_resolution[1]))
		if return_code != 0:
			self.debug_message("Resize operation failed!")
			return "FAIL"

		# Get non-extension part of filename.
		file_basename = filename[:-4]

		# Construct SSDV command-line.
		ssdv_command = "ssdv -e -n -q %d -c %s -i %d picam_temp.jpg picam_temp.ssdv" % (quality, self.callsign, image_id)
		print(ssdv_command)
		# Update debug message.
		self.debug_message("Converting image to SSDV.")

		# Run SSDV converter.
		return_code = os.system(ssdv_command)

		if return_code != 0:
			self.debug_message("ERROR: Could not perform SSDV Conversion.")
			return "FAIL"
		else:
			return "picam_temp.ssdv"

	auto_capture_running = False
	def auto_capture(self, destination_directory, tx, post_process_ptr=None, delay = 0, start_id = 0):
		""" Automatically capture and transmit images in a loop.
		Images are automatically saved to a supplied directory, with file-names
		defined using a timestamp.

		Use the run() and stop() functions to start/stop this running.
		
		Keyword Arguments:
		destination_directory:	Folder to save images to. Both raw JPEG and SSDV images are saved here.
		tx:		A reference to a PacketTX Object, which is used to transmit packets, and interrogate the TX queue.
		post_process_ptr: An optional function which is called after the image is captured. This function
						  will be passed the path/filename of the captured image.
						  This can be used to add overlays, etc to the image before it is SSDVified and transmitted.
						  NOTE: This function need to modify the image in-place.
		delay:	An optional delay in seconds between capturing images. Defaults to 0.
				This delay is added on top of any delays caused while waiting for the transmit queue to empty.
		start_id: Starting image ID. Defaults to 0.
		"""

		image_id = start_id

		while self.auto_capture_running:
			# Sleep before capturing next image.
			sleep(delay)

			# Grab current timestamp.
			capture_time = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%SZ")
			capture_filename = destination_directory + "/%s_picam.jpg" % capture_time

			# Attempt to capture.
			capture_successful = self.capture(capture_filename)

			# If capture was unsuccessful, try again in a little bit
			if not capture_successful:
				sleep(5)

				self.debug_message("Capture failed! Attempting to reset camera...")

				try:
					self.cam.close()
				except:
					self.debug_message("Closing camera object failed.")

				try:
					self.init_camera()
				except:
					self.debug_message("Error initializing camera!")
					sleep(1)

				continue

			# Otherwise, proceed to post-processing step.
			if post_process_ptr != None:
				try:
					self.debug_message("Running Image Post-Processing")
					post_process_ptr(capture_filename)
				except:
					error_str = traceback.format_exc()
					self.debug_message("Image Post-Processing Failed: %s" % error_str)

			# SSDV'ify the image.
			ssdv_filename = self.ssdvify(capture_filename, image_id=image_id)

			# Check the SSDV Conversion has completed properly. If not, continue
			if ssdv_filename == "FAIL":
				sleep(1)
				continue


			# Otherwise, read in the file and push into the TX buffer.
			file_size = os.path.getsize(ssdv_filename)

			# Wait until the transmit queue is empty before pushing in packets.
			self.debug_message("Waiting for SSDV TX queue to empty.")
			while tx.image_queue_empty() == False:
				sleep(0.05) # Sleep for a short amount of time.
				if self.auto_capture_running == False:
					return

			# Inform ground station we are about to send an image.
			self.debug_message("Transmitting %d PiCam SSDV Packets." % (file_size//256))

			# Push SSDV file into transmit queue.
			tx.queue_image_file(ssdv_filename)

			# Increment image ID.
			image_id = (image_id + 1) % 256
		# Loop!

		self.debug_message("Uh oh, we broke out of the main thread. This is not good!")


	def run(self, destination_directory, tx, post_process_ptr=None, delay = 0, start_id = 0):
		""" Start auto-capturing images in a thread.

		Refer auto_capture function above.
		
		Keyword Arguments:
		destination_directory:	Folder to save images to. Both raw JPEG and SSDV images are saved here.
		tx:		A reference to a PacketTX Object, which is used to transmit packets, and interrogate the TX queue.
		post_process_ptr: An optional function which is called after the image is captured. This function
						  will be passed the path/filename of the captured image.
						  This can be used to add overlays, etc to the image before it is SSDVified and transmitted.
						  NOTE: This function need to modify the image in-place.
		delay:	An optional delay in seconds between capturing images. Defaults to 0.
				This delay is added on top of any delays caused while waiting for the transmit queue to empty.
		start_id: Starting image ID. Defaults to 0.
		"""		

		self.auto_capture_running = True

		capture_thread = Thread(target=self.auto_capture, kwargs=dict(
			destination_directory=destination_directory,
			tx = tx,
			post_process_ptr=post_process_ptr,
			delay=delay,
			start_id=start_id))

		capture_thread.start()

	def stop(self):
		self.auto_capture_running = False

	# TODO: Non-blocking image capture.
	capture_finished = False
	def trigger_capture():
		pass


# Basic transmission test script.
if __name__ == "__main__":
	import PacketTX
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("callsign", default="N0CALL", help="Payload Callsign")
	parser.add_argument("--txport", default="/dev/ttyAMA0", type=str, help="Transmitter serial port. Defaults to /dev/ttyAMA0")
	parser.add_argument("--baudrate", default=115200, type=int, help="Transmitter baud rate. Defaults to 115200 baud.")
	args = parser.parse_args()

	callsign = args.callsign
	print("Using Callsign: %s" % callsign)

	def post_process(filename):
		print("Doing nothing with %s" % filename)

	tx = PacketTX.PacketTX(serial_port=args.txport, serial_baud=args.baudrate, callsign=callsign)
	tx.start_tx()


	picam = WenetPiCam(src_resolution=(1920,1088), 
		tx_resolution=(1920,1088), 
		callsign=callsign, 
		num_images=5, 
		debug_ptr=tx.transmit_text_message, 
		vertical_flip=False, 
		horizontal_flip=False)

	picam.run(destination_directory="./tx_images/", 
		tx = tx,
		post_process_ptr = post_process
		)
	try:
		while True:
			tx.transmit_text_message("Waiting...")
			sleep(5)
	except KeyboardInterrupt:
		print("Closing")
		picam.stop()
		tx.close()

