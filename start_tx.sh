#!/bin/bash
#
#	Wenet TX-side Initialisation Script
#	2022-03-19 Mark Jessop <vk5qi@rfhead.net>
#
#	Run this to set up an attached RFM22B/RFM98W and start transmitting!
#	Replace the transmit frequency and callsign with your own.
#

# A callsign which will be included in the Wenet Packets.
# This MUST be <= 6 characters long.
MYCALL=N0CALL

# The centre frequency of the Wenet transmission.
TXFREQ=443.500

# Baud Rate
# Known working transmit baud rates are 115200 (the preferred default).
# Lower baud rates *may* work, but will need a lot of testing on the receiver
# chain to be sure they perform correctly.
BAUDRATE=115200

# GPS Port
# Note that we only support uBlox GPS units
GPSPORT=/dev/ttyACM0

# CHANGE THE FOLLOWING LINE TO REFLECT THE ACTUAL PATH TO THE TX FOLDER.
# i.e. it may be /home/username/dev/wenet/tx/
cd /home/pi/wenet/tx/

#Uncomment to initialise a RFM22B (untested with Python 3)
#python init_rfm22b.py $TXFREQ
# Uncomment for use with a RFM98W
python3 init_rfm98w.py --frequency $TXFREQ --baudrate $BAUDRATE

# Start the main TX Script.
# Note that you can also add --logo /path/to/logo.png  to this to add a logo overlay.
python3 tx_picam_gps.py --baudrate $BAUDRATE --gps $GPSPORT $MYCALL &

# If you don't want any GPS overlays, you can comment the above line and run:
# python WenetPiCam.py --baudrate $BAUDRATE $MYCALL &
