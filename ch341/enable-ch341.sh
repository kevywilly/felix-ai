#!/bin/bash

ssh orin1
sudo apt-get update
sudo apt-get install libssl-dev
head -n 1 /etc/nv_tegra_release # use for below url
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v3.0/sources/public_sources.tbz2
mkdir ~/jetson_kernel
cd ~/jetson_kernel
tar -xvf public_sources.tbz2
cd Linux_for_Tegra/source/public
tar -xvf source/kernel_src.tbz2
cd kernel/kernel-5.10

zcat /proc/config.gz > ~/config.bak
zcat /proc/config.gz > .config

make menuconfig

# - Navigate through the menus:

#  - **Device Drivers** → **USB support** → **USB Serial Converter support**

#- Enable the following options:

#  - **USB Serial Converter support** (`CONFIG_USB_SERIAL`):
#    - Set as module (recommended): `[M]`
#  - **USB CP210x family of USB to serial converters** (`CONFIG_USB_SERIAL_CP210X`):
#    - Set as module: `[M]`
#  - **USB Winchiphead CH341 Single Port Serial Driver** (`CONFIG_USB_SERIAL_CH341`):
#    - Set as module: `[M]`


uname -r # use for localversion
export LOCALVERSION="-tegra"

make prepare
make modules_prepare
make -j$(nproc) modules

sudo make modules_install

sudo depmod -a
