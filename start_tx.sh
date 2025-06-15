#!/bin/bash
#
#	Wenet TX-side Initialisation Script
#	2024-09-14 Mark Jessop <vk5qi@rfhead.net>
#
#	Run this to set up an attached RFM98W and start transmitting!
#	Replace the transmit frequency and callsign with your own.
#
#

# A callsign which will be included in the Wenet Packets.
# This MUST be <= 6 characters long.
MYCALL=N0CALL

# The centre frequency of the Wenet transmission, in MHz.
TXFREQ=443.500

# Transmit power, in dBm
# Allowed values are from 2 through 17 dBm.
TXPOWER=17

# GPS Port and baud rate
# Note that we only support uBlox GPS units
# set this to none to disable GPS support
GPSPORT=/dev/ttyACM0
GPSBAUD=115200

# Image settings
# Image scaling - Scale the 'native' image resolution of the attached camera by this much
# before transmitting.
TX_IMAGE_SCALING=0.5

# White Balance settings
# Allowed Values: Auto, Daylight, Cloudy, Incandescent, Tungesten, Fluorescent, Indoor
WHITEBALANCE=Auto

# Exposure compensation
# Allowed values: -8.0 to 8.0
# You may wish to adjust this to bump up the exposure a little.
EXPOSURE=0.0

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

# OPTIONAL - Wait for the GNSS receiver to obtain lock before starting up the camera and transmitter.
# This may help with getting first GNSS lock after boot.
# --waitforlock 10      Wait for up to 10 minutes before timing out and continuing anyway
# --lockcount 60        Wait for 60 sequential valid 3D fixed before exiting (2 Hz update rate, so 60 -> 30 seconds)
# --locksats 6          Only consider a fix as valid if it has more than 6 SVs in use.
#python3 ublox.py --waitforlock 10 --lockcount 60 --locksats 6 --baudrate $GPSBAUD $GPSPORT


# Start the main TX Script.
#
# Additional configuration lines you may wish to add or remove before the $CALLSIGN line may include:
# Flip the image vertically and horizontally (e.g. if the camera is mounted upside down)
# --vflip --hflip \
#
# Add a logo overlay in the bottom right of the image. This must be a transparent PNG file.
# --logo yourlogo.png \
#
# Set a fixed focus position on a PiCam v3 (NOTE: The Picamv3 focus drifts with temperature - beware!!!)
# 0.0 = Infinity
# --lensposition 0.0 \
#
# Set a user-defined AutoFocus Window Area, for use wiith PiCam v3 in Autofocus Mode
# Must be provided as x,y,w,h  , with all values between 0-1.0, where:
# x: Starting X position of rectangle within frame, as fraction of frame width
# y: Starting Y position of rectangle within frame, as fraction of frame height
# w: Width of rectangle, as fraction of frame width
# h: Height of rectangle, as fraction of frame height
# e.g:
# --afwindow 0.25,0.25,0.5,0.5 \
#
# Set a custom focus mapping range for the PiCam v3, which maps the autofocus range to a lens position.
# This can be used to constrain the autofocus range, or even completely unlock it to the full lens travel.
# e.g., for full lens travel, use: 
# --afcustommap 0.0,0.0,15.0,1024.0 \
#
#
# Use the Focus Figure-of-merit metadata to select the transmitted image, instead of selecting on file size
# Only useful for lenses with autofocus (PiCam v3)
# --use_focus_fom

python3 tx_picamera2_gps.py \
    --rfm98w $SPIDEVICE \
    --baudrate $BAUDRATE \
    --frequency $TXFREQ \
    --serial_port $SERIALPORT \
    --tx_power $TXPOWER \
    --gps $GPSPORT \
    --gpsbaud $GPSBAUD \
    --resize $TX_IMAGE_SCALING \
    --whitebalance $WHITEBALANCE \
    --exposure $EXPOSURE \
    $MYCALL
