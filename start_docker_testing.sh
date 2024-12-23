# /usr/bin/env bash
#
# Helper script to start up the Wenet Docker image.
#
# This script is intended to be downloaded using wget or otherwise,
# and modified prior to use.
#

# Your station callsign, which will be shown on https://ssdv.habhub.org
# when receiving packets.
# Make sure there is no space between the = and your callsign.
MYCALL=CHANGEME

# Receive Frequency (Hz)
# The normal receive frequency used by Project Horus is 443.5 MHz
RXFREQ=443500000

# SDR Type. Set this to RTLSDR for RTL-SDR use or KA9Q for KA9Q-Radio use
SDR_TYPE=RTLSDR

# RTLSDR Device ID. Leave this at 0 if you don't want to use a particular device
DEVICE=0

# Receiver Gain (RTL-SDR only). Set this to 0 to use automatic gain control, otherwise if running a
# preamplifier, you may want to experiment with lower gain settings to optimize
# your receiver setup.
# You can find what gain range is valid for your RTLSDR by running: rtl_test
# A very rough figure that may work if you are running a preamp with ~20 dB gain is
# 32.8 - your performance may vary!
GAIN=0

# Bias Tee Enable (1) or Disable (0) (RTL-SDR only)
# Enable this is you are intending on powering a preamplifer via coax from your RTLSDR
BIAS=0


# Baud Rate & FSK Demod Oversampling Settings
#
# Default: 115177 baud 8x oversampling (Default using a RPi Zero W's UART)
# Other parameters which *may* work, but are un-tested:
# 9600 baud, 100x oversampling
# 4800 baud, 200x oversampling
#
BAUD_RATE=115177
OVERSAMPLING=8


# UDP Payload Summary
# Default: 0 (disabled)
# Set this to a valid UDP port (55673 typically) to emit payload summary packets for use
# with Chasemapper
UDP_PORT=0

# UDP Port used for Wenet inter-process communication.
# If you are intenting on running more than one Wenet instance on the same computer
# (e.g. multiple docker containers), use a different port for each instance.
IMAGE_PORT=7890

# HTTP server port for Web GUI.
# If you are intenting on running more than one Wenet instance on the same computer
# (e.g. multiple docker containers), use a different port for each instance.
WEB_PORT=5003

# Stop and remove any existing wenet instances
echo "Stopping/Removing any existing Wenet instances..."
docker stop wenet || true && docker rm wenet || true

# Start the container!
echo "Starting new Wenet instance..."
if [ "$SDR_TYPE" = "RTLSDR" ] ; then
	docker run -d \
		--name wenet \
		-e MYCALL=$MYCALL \
		-e RXFREQ=$RXFREQ \
		-e GAIN=$GAIN \
		-e BIAS=$BIAS \
		-e BAUD_RATE=$BAUD_RATE \
		-e OVERSAMPLING=$OVERSAMPLING \
		-e DEVICE=$DEVICE \
		-e UDP_PORT=$UDP_PORT \
		-e IMAGE_PORT=$IMAGE_PORT \
		-e WEB_PORT=$WEB_PORT \
		-e SDR_TYPE=$SDR_TYPE \
		-v ~/wenet/rx_images/:/opt/wenet/rx_images/ \
		--device /dev/bus/usb \
		-p $WEB_PORT:$WEB_PORT \
		--restart="always" \
		ghcr.io/projecthorus/wenet:testing
elif [ "$SDR_TYPE" = "KA9Q" ] ; then
	docker run -d \
		--name wenet \
		-e MYCALL=$MYCALL \
		-e RXFREQ=$RXFREQ \
		-e GAIN=$GAIN \
		-e BIAS=$BIAS \
		-e BAUD_RATE=$BAUD_RATE \
		-e OVERSAMPLING=$OVERSAMPLING \
		-e DEVICE=$DEVICE \
		-e UDP_PORT=$UDP_PORT \
		-e IMAGE_PORT=$IMAGE_PORT \
		-e WEB_PORT=$WEB_PORT \
		-e SDR_TYPE=$SDR_TYPE \
		-v ~/wenet/rx_images/:/opt/wenet/rx_images/ \
		-v /var/run/dbus:/var/run/dbus \
		-v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
		--device /dev/bus/usb \
		--network host \
		--restart="always" \
		ghcr.io/projecthorus/wenet:testing

else
	echo "No valid SDR type specified! Please enter RTLSDR or KA9Q!"
	exit 0
fi

echo "Navigate to http://localhost:5003/ in your web browser to see the Wenet interface!"
