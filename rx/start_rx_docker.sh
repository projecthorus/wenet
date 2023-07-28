#!/bin/bash
#
#	Wenet RX-side Initialisation Script - HEADLESS DOCKER VERSION
#	2022 Mark Jessop <vk5qi@rfhead.net>
#
#	This code mostly assumes an RTLSDR will be used for RX.
#
#	This version of the startup script is intended to be run as a Docker container
# on a headless Raspberry Pi 3B+ or newer.
#	A display of imagery and telemetry can be accessed at http://<pi_ip>:5003/
#

# Check that a callsign has been set.
if [ -z "$MYCALL" ]; then
  echo "ERROR: MYCALL has not been set."
	exit 1
fi

# Defaults
: "${RXFREQ:=443500000}"
: "${DEVICE:=0}"
: "${GAIN:=0}"
: "${BIAS:=0}"
: "${BAUD_RATE:=115177}"
: "${OVERSAMPLING:=8}"

# Start up the SSDV Uploader script and push it into the background.
python3 ssdvuploader.py "$MYCALL" &
SSDV_UPLOAD_PID=$!

# Start the Web Interface Server
python3 wenetserver.py "$MYCALL" &
WEB_VIEWER_PID=$!

# Calculate the SDR sample rate required.
SDR_RATE=$(("$BAUD_RATE" * "$OVERSAMPLING"))

# Calculate the SDR centre frequency.
# The fsk_demod acquisition window is from Rs/2 to Fs/2 - Rs.
# Given Fs is Rs * Os  (Os = oversampling), we can calculate the required tuning offset with the equation:
# Offset = Fcenter - Rs*(Os/4 - 0.25)
RX_SSB_FREQ=$(echo "$RXFREQ - $BAUD_RATE * ($OVERSAMPLING/4 - 0.25)" | bc)

echo "Using SDR Sample Rate: $SDR_RATE Hz"
echo "Using SDR Centre Frequency: $RX_SSB_FREQ Hz"

if [ "$BIAS" = "1" ]; then
  echo "Enabling Bias Tee"
  rtl_biast -d "$DEVICE" -b 1
fi

# Start up the receive chain.
echo "Using Complex Samples."
rtl_sdr -d "$DEVICE" -s "$SDR_RATE" -f "$RX_SSB_FREQ" -g "$GAIN" - | \
./fsk_demod --cu8 -s --stats=100 2 "$SDR_RATE" "$BAUD_RATE" - - 2> >(python3 fskstatsudp.py --rate 1 --freq $RX_SSB_FREQ --samplerate $SDR_RATE) | \
./drs232_ldpc - -  -vv 2> /dev/null | \
python3 rx_ssdv.py --partialupdate 16 --headless

# Kill off the SSDV Uploader and the GUIs
kill $SSDV_UPLOAD_PID
kill $WEB_VIEWER_PID
