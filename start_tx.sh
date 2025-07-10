#!/bin/bash
cd /root/wenet/tx/

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

/usr/bin/ubxtool  -f /dev/ttySOFT0  -v 3 -s 9600 -e binary -d NMEA -S 4800 -w 5
/usr/bin/python3 /root/agps.py
/usr/bin/python3 ublox.py --waitforlock 10 --lockcount 60 --locksats 2 --baudrate 4800 /dev/ttySOFT0
/usr/bin/python3 tx_picamera2_gps.py --rfm98w 1 --frequency=443.500 --baudrate=115200 --rfm98w-i2s 1 --frequency=443.500 --baudrate=96000 -v  --gpsbaud 4800 --gps /dev/ttySOFT0 VK3FUR VK4XSS
