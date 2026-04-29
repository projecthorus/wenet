# WENET tx Hat by Tynet.eu

Because the recommended pi hats for building WENETV2 TX hardware are not easy to come by in europe and need to be modified i designed my own hat.

This is based on the Adafruit design and in general quite simple, it needs no modification cable because it's just amde for WENET tranmitting.

You can either use the files in this folder to order some PCBs on JLCPCB or ask me (do5ty@darc.de) if there is a baord avaliable for purchase.

* made for Wenet, no modifications needed
* simple to assemble
* flight proven at the FUNK.TAG Kassel 2026
* made for RFM98W modules
* UART header for conencting a GPS (BN220 for example)
* 5V header for external devices
* IPEX conenctor for TX antenna

## Getting it ready for flight

The PCB should look like this if you get them froma factory like JLCPCB, you only need to add the RFM98W module as well as the header that connects to the raspebbry pi.

![PCB from the factory](/hardware/PCB_TYNET_WENET_TX_HAT_V1.jpg)

In my case i also added a BN220 GPS to the serial port for my flight, this will directly conenct over the pin header to the pi and can be used with the tx script.
For the flight i used this hat on a PiZero2 W and a Picam 2 as well as a groundplane antenna at the bottom of the payload.
The maximum received range was over 300km on this first flight of the hardware.

![Ready to fly hat on PiZero2 W](/hardware/RTF_TYNET_WENET_TX_HAT_V1.jpg)
