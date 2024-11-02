#!/usr/bin/env python
#
#   Wenet SSDV Upload Class
#
#   Copyright (C) 2019  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#   Somewhat more robust SSDV Uploader class, which can be instantiated from within 
#   another application and monitored.
#   Compatible with both Python 2 and Python 3
#

import argparse
import datetime
import logging
import json
import os
import glob
import requests
import socket
import sys
import time
import traceback
from base64 import b64encode
from threading import Thread, Lock
try:
    # Python 2
    from Queue import Queue
except ImportError:
    # Python 3
    from queue import Queue

from WenetPackets import WENET_IMAGE_UDP_PORT


class SSDVUploader(object):
    """
    Queued SSDV Imagery Uploader Class

    Based on the Queued habitat uploader class from auto_rx.

    """


    SSDV_URL = "http://ssdv.habhub.org/api/v0/packets"

    def __init__(self,
        uploader_callsign = "N0CALL",
        enable_file_watch = True,
        watch_directory = "./rx_images/",
        file_mask = "*.bin",
        watch_time = 5,
        queue_size = 8192,
        upload_block_size = 256,
        upload_timeout = 20,
        upload_retries = 3,
        upload_anyway = 10
        ):
        """
        Initialise a SSDV Uploader Object
        
        Args:


            upload_retries (int): How many times to retry an upload on a timeout before discarding.


        """

        self.uploader_callsign = uploader_callsign
        self.upload_block_size = upload_block_size
        self.upload_timeout = upload_timeout
        self.upload_retries = upload_retries
        self.upload_anyway = upload_anyway
        self.watch_time = watch_time

        # Generate search mask.
        self.search_mask = os.path.join(watch_directory, file_mask)

        # Set up Queue
        self.upload_queue = Queue(queue_size)

        # Count of uploaded packets.
        self.upload_count = 0
        # Count of discarded packets due to upload failures.
        self.discard_count = 0


        # Start uploader and file watcher threads.
        self.uploader_running = True

        self.uploader_thread = Thread(target=self.uploader_loop)
        self.uploader_thread.start()

        if enable_file_watch:
            self.file_watch_thread = Thread(target=self.file_watch_loop)
            self.file_watch_thread.start()



    def ssdv_encode_packet(self, packet):
        ''' Convert a packet to a suitable JSON blob. '''
        _packet_dict = {
            "type" :    "packet",
            "packet" :  b64encode(packet).decode('ascii'), # Note - b64encode accepts bytes objects under Python 3, and strings under Python 2.
            "encoding": "base64",
            # Because .isoformat() doesnt give us the right format... (boo)
            "received": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "receiver": self.uploader_callsign,
        }

        return _packet_dict


    def ssdv_upload_single(self, packet):
        _packet_dict = self.ssdv_encode_packet(packet)

        _attempts = 1
        while _attempts <= self.upload_retries:
            try:
                _r = requests.post(self.SSDV_URL, json=_packet_dict, timeout=self.upload_timeout)
                return True

            except requests.exceptions.Timeout:
                # Timeout! We can re-try.
                _attempts += 1
                continue

            except Exception as e:
                logging.error("Uploader - Error when uploading: %s" % str(e))
                break

        return False


    def ssdv_upload_multiple(self, count):
        # Sanity check that there are enough packet in the queue to upload.
        if count > self.upload_queue.qsize():
            count = self.upload_queue.qsize()

        _encoded_array = []

        for i in range(count):
            _encoded_array.append(self.ssdv_encode_packet(self.upload_queue.get()))

        _packet_dict = {
            "type": "packets",
            "packets": _encoded_array
        }

        _attempts = 1
        while _attempts <= self.upload_retries:
            try:
                _r = requests.post(self.SSDV_URL, json=_packet_dict, timeout=self.upload_timeout)
                logging.debug("Uploader - Successfuly uploaded %d packets." % count)
                return True

            except requests.exceptions.Timeout:
                # Timeout! We can re-try.
                _attempts += 1
                logging.debug("Uploader - Upload Timeout (attempt %d/%d)." % (_attempts, self.upload_retries))
                continue

            except Exception as e:
                logging.error("Uploader - Error when uploading: %s" % str(e))
                return False

        logging.error("Uploader - Upload timed out after %d attempts." % _attempts)
        return False


    def uploader_loop(self):
        logging.info("Uploader - Started uploader thread.")


        _last_upload_time = time.time()

        while self.uploader_running:

            if self.upload_queue.qsize() >= self.upload_block_size:

                if self.ssdv_upload_multiple(self.upload_block_size):
                    # Upload successful!
                    self.upload_count += self.upload_block_size
                else:
                    # The upload has failed, 
                    self.discard_count += self.upload_block_size

                _last_upload_time = time.time()

            elif (self.upload_queue.qsize() > 0) and ( (time.time() - _last_upload_time) > self.upload_anyway):
                # We have some packets in the queue, and haven't uploaded in a while. Upload them.
                _packet_count = self.upload_queue.qsize()

                if self.ssdv_upload_multiple(_packet_count):
                    # Upload successful!
                    self.upload_count += _packet_count
                else:
                    # The upload has failed, 
                    self.discard_count += _packet_count

                _last_upload_time = time.time()

            time.sleep(1)


        logging.info("Uploader - Closed uploader thread.")



    def file_watch_loop(self):
        logging.info("Directory Watcher - Started Directory Watcher Thread.")

        _rx_images = glob.glob(self.search_mask)
        _rx_images.sort()

        while self.uploader_running:

            # Wait a few seconds before checking for new files.
            time.sleep(self.watch_time)

            # Check for new files.
            _folder_check = glob.glob(self.search_mask)

            if len(_folder_check) == 0:
                # No files in directory, continue.
                continue

            # Sort list. Image filenames are timestamps, so the last element in the array will be the latest image.
            _folder_check.sort()

            # Determine which images are new
            _folder_check = set(_folder_check)
            _new_images = [x for x in _folder_check if x not in _rx_images]
            _new_images.sort()

            for _image in _new_images:
                # New file! Wait a short amount of time in case the file is still being written out.
                time.sleep(0.5)

                # Add it to the queue!
                try:
                    self.add_file(_image)
                except Exception as e:
                    logging.error("Directory Watcher - Error when adding image: %s" % str(e))

                # Update the list of uploaded images
                _rx_images.append(_image)





            time.sleep(1)


        logging.info("Directory Watcher - Closed Directory Watch Thread.")


    def get_queue_size(self):
        """ Return the packets remaining in the queue """
        return self.upload_queue.qsize()


    def get_upload_count(self):
        """ Return the total number of packets uploaded so far """
        return self.upload_count


    def get_discard_count(self):
        """ Return the total number of packets uploaded so far """
        return self.discard_count


    def add_packet(self, data):
        """ Add a single packet to the uploader queue. 
            If the queue is full, the packet will be immediately discarded.

            Under Python 2, this function should be passed strings.
            Under Python 3, it should be passed bytes objects.
        """
        if len(data) == 256:
            try:
                self.upload_queue.put_nowait(data)
                return True
            except:
                # Queue was full.
                self.discard_count += 1
                if self.discard_count % 256 == 0:
                    logging.warning("Upload Queue Full - Packets are being dropped.")
                return False


    def add_file(self, filename):
        """ Attempt to add a file to the upload queue """

        _file_size = os.path.getsize(filename)

        if _file_size%256 != 0:
            logging.error("Directory Watcher - %s size (%d) not a multiple of 256, likely not a SSDV file." % (filename, _file_size))
            return False

        _packet_count = _file_size // 256

        logging.info("Directory Watcher - New file %s contains %d packets." % (filename, _packet_count))

        _packets_added = 0

        _f = open(filename, 'rb')

        for _i in range(_packet_count):
            _packet = _f.read(256)

            if self.add_packet(_packet):
                _packets_added += 1

        _f.close()

        logging.info("Directory Watcher - Added %d packets to queue." % _packets_added)


    def close(self):
        """ Stop uploader thread. """
        logging.info("Shutting down threads.")
        self.uploader_running = False



def telemetry_gui_update(queued, uploaded, discarded):
    """ Update the SSDV Receiver GUI with information on how many packets have been uploader """
    message =   {'uploader_status': 'running',
                'queued': queued,
                'uploaded': uploaded,
                'discarded': discarded
                }

    try:
        gui_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        gui_socket.sendto(json.dumps(message).encode('ascii'), ("127.0.0.1", WENET_IMAGE_UDP_PORT))
        gui_socket.close()

    except Exception as e:
        logging.error("Error updating GUI with uploader status: %s" % str(e))




if __name__ == "__main__":

    # Command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument("callsign", default="WENETRX", help="User Callsign")
    parser.add_argument("--watch_dir", default="./rx_images/", help="Directory to watch for new files. (Default: ./rx_images/")
    parser.add_argument("--file_mask", default="*.bin", help="File mask to watch (Defaut: *.bin)")
    parser.add_argument("--queue_size", default=8192, type=int, help="Uploader queue size (Default: 8192 packets = ~2MiB)")
    parser.add_argument("--upload_block_size", default=256, type=int, help="Upload block size (Default: 256 packets uploaded at a time.)")
    parser.add_argument("--image_port", type=int, default=None, help="UDP port used for communication between Wenet decoder processes. Default: 7890")
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Verbose logging output.")
    args = parser.parse_args()

    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO


    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)
    logging.getLogger("requests").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)


    # Overwrite the image UDP port if it has been provided
    if args.image_port:
        WENET_IMAGE_UDP_PORT = args.image_port

    _uploader = SSDVUploader(
        uploader_callsign = args.callsign,
        watch_directory = args.watch_dir,
        file_mask = args.file_mask,
        queue_size = args.queue_size,
        upload_block_size = args.upload_block_size)

    try:
        while True:
            time.sleep(5)
            logging.debug("%d packets in uploader queue, %d packets uploaded, %d packets discarded." % (_uploader.get_queue_size(), _uploader.get_upload_count(), _uploader.get_discard_count()))
            telemetry_gui_update(_uploader.get_queue_size(), _uploader.get_upload_count(), _uploader.get_discard_count())
    except KeyboardInterrupt:
        _uploader.close()

