#!/bin/bash


# Make sure we're in the right directory.
cd ~/wenet/tx/

# Build LDPC Encoder Library
echo "Building LDPC Encoder Library."
gcc -fPIC -shared -o ldpc_enc.so ldpc_enc.c

# Build i2s drivers
cd i2smaster

echo "Building I2S Driver"
dtc -@ -H epapr -O dtb -o i2smaster.dtbo -Wno-unit_address_vs_reg i2smaster.dts

# Install driver
echo "Installing I2S Driver (requires sudo)"
sudo cp i2smaster.dtbo /boot/overlays


cd ~/wenet/tx/
echo "Now continue with the instructions to modify your /boot/firmware/config.txt file to enable I2S."
