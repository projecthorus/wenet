# Wenet - The Swift One
Transmit and Receive code for the Project Horus High-Speed Imagery Payload - 'Wenet'.

![Image downlinked via Wenet on Horus 42](http://rfhead.net/temp/horus_42_small.jpg)

The above image was captured on Horus 42, and downlinked via Wenet. The original downlinked resolution was 1920x1440, and has since been re-sized. The full resolution version is available here: http://rfhead.net/temp/horus_42_full.jpg

## What is it?
Wenet is a radio modem designed to downlink imagery from High-Altitude Balloon launches. It uses Frequency-Shift-Keying (FSK) at a rate of ~115kbit/s, and uses LDPC forward-error-correction to provide 6 dB of coding gain.

The transmit side is designed to run on a Raspberry Pi, and the UART is used to modulate a HopeRF RFM98W in direct-asynchronous FSK mode. We usually operate in the quieter 440-450 MHz portion of the amateur 70cm band, with our nominal frequency being 443.5 MHz. Due to the non-ideal filtering in the transmitter module the [occupied bandwidth](https://github.com/projecthorus/wenet/raw/master/doc/occupied_bw.png) is ~300 kHz, so Wenet is not suitable for operation in the 434 MHz ISM band. The usual [transmit power](https://raw.githubusercontent.com/projecthorus/wenet/master/doc/tx_power.png) we use is 50mW, into an inverted 1/4-wave monopole underneath the payload. Details on the modulation and packet formats are [available here](https://github.com/projecthorus/wenet/wiki/Modem-&-Packet-Format-Details).

The receiver side makes used of Software Defined Radio (in particular, RTLSDR dongles), and a high performance FSK modem written by [David Rowe](http://rowetel.com/). Received images are available locally via a web interface, and are also uploaded to https://ssdv.habhub.org/ where packets contributed by many stations can be used to form a complete image live during a flight.

Bench [testing](https://www.rowetel.com/?p=5080) has shown that for a receiver with a Noise Figure of 2dB (e.g. a RTLSDR with a separate low-noise preamplifier), a minimum detectable signal of ~-112 dBm is required for reliable reception of imagery. Reception at > 100km ranges is acheivable using a short yagi antenna (5 elements). The current reception range record is 480km, using an 18-element yagi antenna and a RTLSDR+Preamp.


### Flight History
* v0.1 - First test flight on Horus 37, no FEC. Read more about that here: http://rfhead.net/?p=637
* v0.2 - Second test flight on Horus 39, with LDPC FEC enabled. Read more here: http://www.rowetel.com/?p=5344
* v0.3 - Third test flight on Horus 40 - 2nd Jan 2017. Added GPS overlay support. Read more here: http://www.areg.org.au/archives/206627
* v0.4 - SHSSP 2017 Launches (Horus 41 & 42) - 22nd Jan 2017. Added IMU and simultaneous capture from two cameras (Visible and Near-IR). Two payloads were flown, each with two cameras. A third payload (same as on Horus 40) was also flown, which captured the image below. Read more here: http://www.areg.org.au/archives/206739
* v0.5 - Minor updates. Flown on Horus 43 through Horus 49.
* v0.6 - Updated to the latest fsk_demod version from codec2-dev. This allows reception without requiring CSDR.
* v0.7 - More tweaks to the start_rx script to better support lower-rate modes. Update to the latest fsk_demod in the instructions.
* v1.0 - Docker image released, documentation updated.

## How do I Receive it?
You can receive Wenet transmissions using a Linux computer, a RTLSDR, and a small yagi antenna (sometimes a vertical can work too). You can find a guide on how to get setup to receive imagery here: https://github.com/projecthorus/wenet/wiki/Wenet-RX-Instructions-(Linux-using-Docker)

## How do I Transmit it?
A guide on setting up a Wenet transmitter using a Raspberry Pi Zero W and a HopeRF RFM98W shield is here: https://github.com/projecthorus/wenet/wiki/Wenet-TX-Payload-Instructions
