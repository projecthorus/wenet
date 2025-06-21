# RaspberryPi_I2S_Master
General I2S master I/O device tree overlay for Raspberry Pi.  
Tested with Raspberry pi Compute Module 3+ and Asahi Kasei AK4558.

- I2S master: Raspberry Pi  
- I2S slave: Audio codec(ex. AK4558)  

[I2S Slave version](https://github.com/AkiyukiOkayasu/RaspberryPi_I2S_Slave)

## How to use  
Compile on Raspberry Pi  
```bash
dtc -@ -H epapr -O dtb -o i2smaster.dtbo -Wno-unit_address_vs_reg i2smaster.dts
```

Copy i2smaster.dtbo to /boot/overlays  
```bash
sudo cp i2smaster.dtbo /boot/overlays
```

Edit /boot/config.txt  
Enable I2S and add i2smaster device tree overlay  
```/boot/config.txt
# Uncomment some or all of these to enable the optional hardware interface
#dtparam=i2c_arm=on
dtparam=i2s=on
#dtparam=spi=on
dtoverlay=i2smaster
```

If you don't need HDMI audio output and Raspberry Pi's headphone output, comment out "dtparam=audio=on" by hash.  
like this.  
```/boot/config.txt
#dtparam=audio=on
```