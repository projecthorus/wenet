TODO - add these details to wiki
### Hardware
Connect [Broadcom pin GPIO 21 / pin 40 on the Pi header](https://pinout.xyz/pinout/pin40_gpio21/) to the DIO2 pin on the RFM98W module.

### Software

#### 0. Install pyalsaaudio

```
sudo apt-get install python3-alsaaudio
```

#### 1. Compile the device tree overlay
```sh
cd tx/i2smaster/
dtc -@ -H epapr -O dtb -o i2smaster.dtbo -Wno-unit_address_vs_reg i2smaster.dts
sudo cp i2smaster.dtbo /boot/overlays
```

#### 2. Edit /boot/firmware/config.txt
Add the following lines
```
dtparam=i2s=on
dtoverlay=i2smaster
```

#### 3. Reboot or load the device tree
```
sudo dtoverlay i2s-master-dac.dtbo 
```

### Troubleshooting
If you've run the UART version of Wenet TX then it's likely that the LED GPIO was accidentlly used. This causes the i2smaster to no longer work. Reboot the Pi and try again.