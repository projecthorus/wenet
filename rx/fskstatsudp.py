#!/usr/bin/env python
#
#   radiosonde_auto_rx - fsk_demod modem statistics parser
#
#   Copyright (C) 2019  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
import argparse
import datetime
import json
import logging
import socket
import sys
import time
import numpy as np
from WenetPackets import WENET_IMAGE_UDP_PORT


class FSKDemodStats(object):
    """
    Process modem statistics produced by fsk_demod and provide access to
    filtered or instantaneous modem data.

    This class expects the JSON output from fsk_demod to be arriving in *realtime*.
    The test script below will emulate relatime input based on a file.
    """


    FSK_STATS_FIELDS = ['EbNodB', 'ppm', 'f1_est', 'f2_est', 'samp_fft']


    def __init__(self,
        averaging_time = 5.0,
        peak_hold = False,
        decoder_id = "",
        freq = 441200000,
        sample_rate = 921416,
        real = False
        ):
        """

        Required Fields:
            averaging_time (float): Use the last X seconds of data in calculations.
            peak_hold (bool): If true, use a peak-hold SNR metric instead of a mean.
            decoder_id (str): A unique ID for this object (suggest use of the SDR device ID)
            
        """

        self.averaging_time = float(averaging_time)
        self.peak_hold = peak_hold
        self.decoder_id = str(decoder_id)
        self.freq = freq
        self.fcentre = 0.0
        self.sample_rate = sample_rate
        self.real = real

        # Input data stores.
        self.in_times = np.array([])
        self.in_snr = np.array([])
        self.in_ppm = np.array([])


        # Output State variables.
        self.snr = -999.0
        self.fest = [0.0,0.0]
        self.fft = []
        self.fft_db = []
        self.fft_freq = []
        self.ppm = 0.0



    def update(self, data):
        """
        Update the statistics parser with a new set of output from fsk_demod.
        This can accept either a string (which will be parsed as JSON), or a dict.

        Required Fields:
            data (str, dict): One set of statistics from fsk_demod.
        """

        # Check input type
        if type(data) == str:
            # Attempt to parse string.
            try:
                # Clean up any nan entries, which aren't valid JSON.
                # For now we just replace these with 0, since they only seem to occur
                # in the eye diagram data, which we don't use anyway.
                if 'nan' in data:
                    data = data.replace('nan', '0.0')

                _data = json.loads(data)
            except Exception as e:
                self.log_error("FSK Demod Stats - %s" % str(e))
                return
        elif type(data) == dict:
            _data = data
        
        else:
            return

        # Check for required fields in incoming dictionary.
        for _field in self.FSK_STATS_FIELDS:
            if _field not in _data:
                self.log_error("Missing Field %s" % _field)
                return

        # Now we can process the data.
        _time = time.time()
        self.fft = np.array(_data['samp_fft'])
        self.fest[0] = _data['f1_est']
        self.fest[1] = _data['f2_est']
        self.fcentre = self.freq + (self.fest[0] + self.fest[1])/2.0

        #self.fft = self.fft[self.fft>0.0]

        try:
            self.fft_db = list(np.around(10*np.log10(self.fft+0.000000001),1))
            self.fft_freq = list(np.around(np.linspace(0, self.sample_rate/2, len(self.fft)) + self.freq, 1))
        except:
            pass

        # Time-series data
        self.in_times = np.append(self.in_times, _time)
        self.in_snr = np.append(self.in_snr, _data['EbNodB'])
        self.in_ppm = np.append(self.in_ppm, _data['ppm'])


        # Calculate SNR / PPM
        _time_range = self.in_times>(_time-self.averaging_time)
        # Clip arrays to just the values we want
        self.in_ppm = self.in_ppm[_time_range]
        self.in_snr = self.in_snr[_time_range]
        self.in_times = self.in_times[_time_range]

        # Always just take a mean of the PPM values.
        self.ppm = np.mean(self.in_ppm)

        if self.peak_hold:
            self.snr = np.max(self.in_snr)
        else:
            self.snr = np.mean(self.in_snr)


    def log_debug(self, line):
        """ Helper function to log a debug message with a descriptive heading. 
        Args:
            line (str): Message to be logged.
        """
        logging.debug("FSK Demod Stats #%s - %s" % (str(self.decoder_id), line))


    def log_info(self, line):
        """ Helper function to log an informational message with a descriptive heading. 
        Args:
            line (str): Message to be logged.
        """
        logging.info("FSK Demod Stats #%s - %s" % (str(self.decoder_id), line))


    def log_error(self, line):
        """ Helper function to log an error message with a descriptive heading. 
        Args:
            line (str): Message to be logged.
        """
        logging.error("FSK Demod Stats #%s - %s" % (str(self.decoder_id), line))



def send_modem_stats(stats):
    """ Send a JSON-encoded dictionary to the wenet frontend """
    try:
        gui_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        gui_socket.sendto(json.dumps(stats).encode('ascii'), ("127.0.0.1", WENET_IMAGE_UDP_PORT))
        gui_socket.close()

    except Exception as e:
        logging.error("Error updating GUI with modem status: %s" % str(e))



if __name__ == "__main__":
    # Command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", default=2, type=int, help="Update Rate (Hz)")
    parser.add_argument("--freq", default=441200000, type=float, help="IQ Centre Frequency (Hz)")
    parser.add_argument("--samplerate", default=921416, type=float, help="Sample rate (Hz)")
    parser.add_argument("--real", default=False, action="store_true", help="Real Samples (not IQ)")
    args = parser.parse_args()

    _averaging_time = 1.0/args.rate

    stats_parser = FSKDemodStats(averaging_time=_averaging_time, peak_hold=True, freq=args.freq, sample_rate=args.samplerate, real=args.real)


    _last_update_time = time.time()

    try:
        while True:
            data = sys.stdin.readline()

            # An empty line indicates that stdin has been closed.
            if data == '':
                break

            # Otherwise, feed it to the stats parser.
            stats_parser.update(data.rstrip())

            if (time.time() - _last_update_time) > _averaging_time:
                # Send latest modem stats to the Wenet frontend.
                _stats = {
                    'snr': stats_parser.snr,
                    'ppm': stats_parser.ppm,
                    #'fft': stats_parser.fft,
                    'fft_db': stats_parser.fft_db,
                    'fft_freq': stats_parser.fft_freq,
                    'fest': stats_parser.fest,
                    'freq': stats_parser.freq,
                    'fcentre': stats_parser.fcentre,
                    'time': datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
                }

                send_modem_stats(_stats)

                _last_update_time = time.time()



    except KeyboardInterrupt:
        pass

