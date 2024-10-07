#!/usr/bin/env python2.7
#
#	Wenet fswebcam Wrapper Class.
#
#	Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#	Released under GNU GPL v3 or later
#

import time
from threading import Thread
import glob
import os
import sys
import datetime

if os.name == 'posix' and sys.version_info[0] < 3:
    import subprocess32 as subprocess
else:
    import subprocess

class WenetFSWebcam(object):
	""" fswebcam Wrapper Class

	fwebcam Image Source for Wenet.
	Captures multiple images (ideally, maybe not), picks the best, then 
	transmits it via a PacketTX object. 

	"""

	def __init__(self,
				fswebcam_config='fswebcam.conf',
				tx_resolution=(1680,1120),
				num_images=1, 
				temp_filename_prefix = 'webcam_temp',
				debug_ptr = None,
				callsign = "N0CALL"):

		""" Instantiate a WenetGPhoto Object
			used to capture images using GPhoto.

			Keyword Arguments:
			callsign: The callsign to be used when converting images to SSDV. Must be <=6 characters in length.
			fswebcam_config: A configuration file containing the desired webcam capture parameters.
							 Refer to the fswebcam man page for more information.

			tx_resolution: Tuple (x,y) containing desired image *transmit* resolution.
						NOTE: both x and y need to be multiples of 16 to be used with SSDV.
						NOTE: This will resize with NO REGARD FOR ASPECT RATIO - it's up to you to get that right.

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
		self.tx_resolution = tx_resolution
		self.fswebcam_config = fswebcam_config

		# Attempt to set camera time.
		# This also tells us if we can communicate with the camera or not.
		proc = subprocess.Popen(['fswebcam','webcam_temp_1.jpg'],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		proc.wait()
		if "No such file or directory" in proc.stderr.read():
			self.debug_message("No Camera Connected!")


	def debug_message(self, message):
		""" Write a debug message.
		If debug_ptr was set to a function during init, this will
		write pass the message to that function, else it will just print it.
		This is used mainly to get updates on image capture into the Wenet downlink.

		"""
		message = "Webcam Debug: " + message
		if self.debug_ptr != None:
			self.debug_ptr(message)
		else:
			print(message)

	def close(self):
		self.cam.close()
		pass

	def capture(self, filename='webcam.jpg'):
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
				start_time = time.time()
				proc = subprocess.Popen(['fswebcam','-c', self.fswebcam_config, temp_filename],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				(proc_stdout, proc_stderr) = proc.communicate(timeout=10)
				#print(proc_stdout)
				#print("stderr:")
				#print(proc_stderr)
				if "Writing JPEG image to" not in proc_stderr:
					self.debug_message("ERROR: Capture Failed.")
					return False
				else:
					print(time.time()-start_time)

			except Exception as e: # TODO: Narrow this down...
				self.debug_message("ERROR: %s" % str(e))
				# Immediately return false. Not much point continuing to try and capture images.
				return False

		
		# Otherwise, continue to pick the 'best' image based on filesize.
		self.debug_message("Choosing Best Image.")
		pic_list = glob.glob("%s_*.jpg" % self.temp_filename_prefix)

		if len(pic_list) == 0:
			self.debug_message("ERROR: No Images Captured!")
			return False

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
		return_code = os.system("convert %s -resize %dx%d\! webcam_temp.jpg" % (filename, self.tx_resolution[0], self.tx_resolution[1]))
		if return_code != 0:
			self.debug_message("Resize operation failed!")
			return "FAIL"

		# Get non-extension part of filename.
		file_basename = filename[:-4]

		# Construct SSDV command-line.
		ssdv_command = "ssdv -e -n -q %d -c %s -i %d webcam_temp.jpg webcam_temp.ssdv" % (quality, self.callsign, image_id)
		print(ssdv_command)
		# Update debug message.
		self.debug_message("Converting image to SSDV.")

		# Run SSDV converter.
		return_code = os.system(ssdv_command)

		if return_code != 0:
			self.debug_message("ERROR: Could not perform SSDV Conversion.")
			return "FAIL"
		else:
			return "webcam_temp.ssdv"

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
			time.sleep(delay)

			# Grab current timestamp.
			capture_time = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%SZ")
			capture_filename = destination_directory + "/%s_webcam.jpg" % capture_time

			# Attempt to capture.
			capture_successful = self.capture(capture_filename)

			# If capture was unsuccessful, wait a few seconds and try and continue,
			# in case the camera is re-connected.
			if not capture_successful:
				time.sleep(10)
				continue

			# Otherwise, proceed to post-processing step.
			if post_process_ptr != None:
				try:
					self.debug_message("Running Image Post-Processing")
					post_process_ptr(capture_filename)
				except:
					self.debug_message("Image Post-Processing Failed.")

			# SSDV'ify the image.
			ssdv_filename = self.ssdvify(capture_filename, image_id=image_id)

			# Check the SSDV Conversion has completed properly. If not, wait a second then continue.
			if ssdv_filename == "FAIL":
				time.sleep(1)
				continue


			# Otherwise, read in the file and push into the TX buffer.
			file_size = os.path.getsize(ssdv_filename)

			# Wait until the transmit queue is empty before pushing in packets.
			self.debug_message("Waiting for SSDV TX queue to empty.")
			while tx.image_queue_empty() == False:
				time.sleep(0.05) # Sleep for a short amount of time.
				if self.auto_capture_running == False:
					return

			# Inform ground station we are about to send an image.
			self.debug_message("Transmitting %d Webcam SSDV Packets." % (file_size/256))

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

	gphoto = WenetFSWebcam(callsign=callsign, debug_ptr=tx.transmit_text_message)

	gphoto.run(destination_directory="./tx_images/", 
		tx = tx,
		post_process_ptr = post_process
		)
	try:
		while True:
			tx.transmit_text_message("Waiting...")
			time.sleep(5)
	except KeyboardInterrupt:
		print("Closing")
		gphoto.stop()
		tx.close()

