#!/usr/bin/env python2.7
#
#	Wenet GPhoto Wrapper Class.
#
#	Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#
#	Uses this libgphoto2 wrapper to avoid USB issues: https://github.com/alexdu/piggyphoto
#	Git clone that repository and copy the 'piggyphoto' directory into wenet/tx/
#
#	WARNING: GPhoto is *really* slow at taking pictures.
#			 Suggest not using the multiple-image mode.
#
#

from time import sleep
from threading import Thread
import glob
import os
import subprocess
import datetime

import piggyphoto


class WenetGPhoto(object):
	""" GPhoto Wrapper Class

	GPhoto Image Source for Wenet.
	Captures multiple images (ideally, maybe not), picks the best, then 
	transmits it via a PacketTX object. 


	"""

	def __init__(self,resolution=(1488,1120), 
				num_images=1, 
				temp_filename_prefix = 'gphoto_temp',
				debug_ptr = None,
				callsign = "N0CALL"):

		""" Instantiate a WenetGPhoto Object
			used to capture images using GPhoto.

			Keyword Arguments:
			callsign: The callsign to be used when converting images to SSDV. Must be <=6 characters in length.
			
			resolution: Tuple (x,y) containing desired image *transmit* resolution.
						NOTE: The raw image from the camera will be saved with whatever resolution is set on the camera.
						NOTE: both x and y need to be multiples of 16 to be used with SSDV.


			num_images: Number of images to capture in sequence when the 'capture' function is called.
						The 'best' (largest filesize) image is selected and saved.

			temp_filename_prefix: prefix used for temporary files.

			debug_ptr:	'pointer' to a function which can handle debug messages.
						This function needs to be able to accept a string.
						Used to get status messages into the downlink.

		"""

		self.debug_ptr = debug_ptr
		self.temp_filename_prefix = temp_filename_prefix
		self.num_images = num_images
		self.callsign = callsign
		self.resolution = resolution

		# Attempt to set camera time.
		# This also tells us if we can communicate with the camera or not.
		proc = subprocess.Popen(['gphoto2','--set-config','datetime=now'],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		proc.wait()
		if "Error" in proc.stderr.read():
			print("Could not communicate with camera!")

		# Now open a 'piggyphoto' (py-gphoto) instance for all further communication.
		self.camera_connected = False
		while not self.camera_connected:
			try:
				self.cam = piggyphoto.camera()
				self.camera_connected = True
			except Exception as e:
				self.debug_message("ERROR: %s - Is the camera connected?" % str(e))
				sleep(5)


	def debug_message(self, message):
		""" Write a debug message.
		If debug_ptr was set to a function during init, this will
		write pass the message to that function, else it will just print it.
		This is used mainly to get updates on image capture into the Wenet downlink.

		"""
		message = "GPhoto Debug: " + message
		if self.debug_ptr != None:
			self.debug_ptr(message)
		else:
			print(message)

	def close(self):
		self.cam.close()
		pass

	def capture(self, filename='gphoto.jpg'):
		""" Capture an image using GPhoto
			
			Keyword Arguments:
			filename:	destination filename.
		"""

		# Attempt to capture a set of images.
		for i in range(self.num_images):
			self.debug_message("Capturing Image %d of %d" % (i+1,self.num_images))
			# Wrap this in error handling in case we lose the camera for some reason.
			try:
				temp_filename = "%s_%d.jpg" % (self.temp_filename_prefix,i)

				self.cam.capture_image(temp_filename)
				# NOTE: This will leave images on the camera! Make sure you have a big SD card...

			except Exception as e: # TODO: Narrow this down...
				self.debug_message("ERROR: %s" % str(e))
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
		self.debug_message("Copying image to storage.")
		os.system("cp %s %s" % (largest_pic, filename))
		# Clean up temporary images.
		os.system("rm %s_*.jpg" % self.temp_filename_prefix)

		return True 

	def ssdvify(self, filename="output.jpg", image_id=0, quality=6):
		""" Convert a supplied JPEG image to SSDV.

		Keyword Arguments:
		filename:	Source JPEG filename.
					Output SSDV image will be saved to this filename, with .jpg replaced by .ssdv
		callsign:	Payload callsign. Max 6 Alphanumeric characters.
		image_id:	Image ID number. Must be incremented between images.
		quality:	JPEG quality level: 4 - 7, where 7 is 'lossless' (not recommended).
					6 provides good quality at decent file-sizes.

		"""

		# Wrap image ID field if it's >255.
		image_id = image_id % 256

		# Resize image to the desired resolution.
		self.debug_message("Resizing image.")
		return_code = os.system("convert %s -resize %dx%d\! gphoto_temp.jpg" % (filename, resolution[0], resolution[1]))
		if return_code != 0:
			self.debug_message("Resize operation failed!")
			return "FAIL"

		# Get non-extension part of filename.
		file_basename = filename[:-4]

		# Construct SSDV command-line.
		ssdv_command = "ssdv -e -n -q %d -c %s -i %d gphoto_temp.jpg gphoto_temp.ssdv" % (quality, self.callsign, image_id)
		print(ssdv_command)
		# Update debug message.
		self.debug_message("Converting image to SSDV.")

		# Run SSDV converter.
		return_code = os.system(ssdv_command)

		if return_code != 0:
			self.debug_message("ERROR: Could not perform SSDV Conversion.")
			return "FAIL"
		else:
			return "gphoto_temp.ssdv"

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
			capture_filename = destination_directory + "/%s_gphoto.jpg" % capture_time

			# Attempt to capture.
			capture_successful = self.capture(capture_filename)

			# If capture was unsuccessful, exit out of this thead, as clearly
			# the camera isn't working.
			if not capture_successful:
				return

			# Otherwise, proceed to post-processing step.
			if post_process_ptr != None:
				try:
					self.debug_message("Running Image Post-Processing")
					post_process_ptr(capture_filename)
				except:
					self.debug_message("Image Post-Processing Failed.")

			# SSDV'ify the image.
			ssdv_filename = self.ssdvify(capture_filename, image_id=image_id)

			# Check the SSDV Conversion has completed properly. If not, break.
			if ssdv_filename == "FAIL":
				return


			# Otherwise, read in the file and push into the TX buffer.
			file_size = os.path.getsize(ssdv_filename)

			# Wait until the transmit queue is empty before pushing in packets.
			self.debug_message("Waiting for SSDV TX queue to empty.")
			while tx.image_queue_empty() == False:
				sleep(0.05) # Sleep for a short amount of time.
				if self.auto_capture_running == False:
					return

			# Inform ground station we are about to send an image.
			self.debug_message("Transmitting %d GPhoto SSDV Packets." % (file_size/256))

			# Push SSDV file into transmit queue.
			tx.queue_image_file(ssdv_filename)

			# Increment image ID.
			image_id = (image_id + 1) % 256
		# Loop!


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
	args = parser.parse_args()

	callsign = args.callsign
	print("Using Callsign: %s" % callsign)

	def post_process(filename):
		print("Doing nothing with %s" % filename)

	tx = PacketTX.PacketTX(callsign=callsign)
	tx.start_tx()

	gphoto = WenetGPhoto(callsign=callsign, debug_ptr=tx.transmit_text_message)

	gphoto.run(destination_directory="./tx_images/", 
		tx = tx,
		post_process_ptr = post_process
		)
	try:
		while True:
			tx.transmit_text_message("Waiting...")
			sleep(5)
	except KeyboardInterrupt:
		print("Closing")
		gphoto.stop()
		tx.close()

