#!/bin/bash
#
#	Wenet TX-side Initialisation Script - Systemd Unit Version
#	2024-07-21 Mark Jessop <vk5qi@rfhead.net>
#
#	Run this to set up an attached RFM98W and start transmitting!
#	Replace the transmit frequency and callsign with your own.
#

# A callsign which will be included in the Wenet Packets.
# This MUST be <= 6 characters long.
MYCALL=N0CALL

# The centre frequency of the Wenet transmission, in MHz.
TXFREQ=443.500

# Transmit power, in dBm
# Allowed values are from 2 through 17 dBm.
TXPOWER=17

# GPS Port
# Note that we only support uBlox GPS units
# set this to none to disable GPS support
GPSPORT=/dev/ttyACM0

# Image settings
# Image scaling - Scale the 'native' image resolution of the attached camera by this much
# before transmitting.
TX_IMAGE_SCALING=0.5

# White Balance settings
# Allowed Values: Auto, Daylight, Cloudy, Incandescent, Tungesten, Fluorescent, Indoor
WHITEBALANCE=Auto

# Refer near the end of this file for image flipping and overlay options

# Baud Rate
# Known working transmit baud rates are 115200 (the preferred default).
# Lower baud rates *may* work, but will need a lot of testing on the receiver
# chain to be sure they perform correctly.
BAUDRATE=115200

# RFM98W SPI Device
# SPI device number of your RFM98W chip
# This will either be 0 or 1 on a RPi.
SPIDEVICE=0

# Modulation UART
# The UART used to modulate the RFM98W with our Wenet transmission
# We want to be using the PL011 UART, *not* the Mini-UART
# On a Pi Zero W, you may need to disable bluetooth. See here for more info:
# https://www.raspberrypi.com/documentation/computers/configuration.html#uarts-and-device-tree
SERIALPORT=/dev/ttyAMA0


# CHANGE THE FOLLOWING LINE TO REFLECT THE ACTUAL PATH TO THE TX FOLDER.
# i.e. it may be /home/username/dev/wenet/tx/
cd /home/pi/wenet/tx/

# Wait here until the SPI devices are available.
# This can take a few tens of seconds after boot.
timeout=20
echo "Checking that the SPI devices exist..."
while : ; do
	[[ -e "/dev/spidev0.0" ]] && break

	if [ "$timeout" == 0 ]; then
		echo "Did not find SPI device in timeout period!"
		exit 1
        # At this point this script exits, and systemd should restart us anyway.
	fi

	echo "Waiting another 2 seconds for SPI to be available."
	sleep 2
	((timeout--))
done

echo "Waiting another 10 seconds before startup."
sleep 10


# Start the main TX Script.
#
# Additional configuration lines you may wish to add or remove before the $CALLSIGN line may include:
# Flip the image vertically and horizontally (e.g. if the camera is mounted upside down)
# --vflip --hflip \
# Add a logo overlay in the bottom right of the image. This must be a transparent PNG file.
# --logo yourlogo.png \
# Set a fixed focus position on a PiCam v3 (NOTE: The Picamv3 focus drifts with temperature - beware!!!)
# --lensposition 0.5 \

python3 tx_picamera2_gps.py \
    --rfm98w $SPIDEVICE \
    --baudrate $BAUDRATE \
    --frequency $TXFREQ \
    --serial_port $SERIALPORT \
    --tx_power $TXPOWER \
    --gps $GPSPORT \
    --resize $TX_IMAGE_SCALING \
    --whitebalance $WHITEBALANCE \
    --vflip --hflip \
    $MYCALL
