# WENET tx Hat by Tynet.eu

Since the recommended Raspberry Pi HATs for building WENETV2 TX hardware are difficult to source in Europe and often require manual modification, I designed my own custom HAT.

The design is based on the original Adafruit layout but remains quite simple. It requires no modification cables because it was purpose-built for WENET transmission.

You can either use the files in this folder to order PCBs from JLCPCB or contact me directly (do5ty@darc.de) to see if I have any assembled boards available for purchase.

* made for Wenet, no modifications needed
* simple to assemble
* flight proven at the [FUNK.TAG Kassel 2026](https://g-fliegt.de/news/start-beim-funk-tag-2026-erfolgreich)
* made for RFM98W modules
* UART header for conencting a GPS (BN220 for example)
* 5V header for external devices
* IPEX conenctor for TX antenna

## Getting it ready for flight

The PCB should look like this if you get them froma factory like JLCPCB, you only need to add the RFM98W module as well as the header that connects to the raspebbry pi.

![PCB from the factory](/hardware/PCB_TYNET_WENET_TX_HAT_V1.jpg)

In my setup, I added a BN-220 GPS module to the serial port for the flight. This connects directly to the Raspberry Pi via the pin header and is fully compatible with the TX script.

For the flight, I used this HAT on a Pi Zero 2 W with a Pi Camera 2 and a ground plane antenna mounted at the bottom of the payload.

The maximum reception range exceeded 300 km during this first flight of the hardware.

![Ready to fly hat on PiZero2 W](/hardware/RTF_TYNET_WENET_TX_HAT_V1.jpg)


## Schematic

![Schematic](/hardware/Schematic_TYNET_WENET_TX_HAT_V1.png)
