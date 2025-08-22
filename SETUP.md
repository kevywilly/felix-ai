
```
sudo apt update
sudo apt install git build-essential dkms linux-headers-$(uname -r)
```

# Install basic build tools first

```
sudo apt update
sudo apt install build-essential git bc kmod
```

# Enable RTL88 WIFI Driver
```
git clone https://github.com/RinCat/RTL88x2BU-Linux-Driver.git
cd RTL88x2BU-Linux-Driver

# Edit the Makefile for ARM64
vi Makefile

CONFIG_PLATFORM_I386_PC = n
CONFIG_PLATFORM_NV_TK1_UBUNTU = y

make clean
make -j$(nproc) ARCH=arm64
sudo make install
sudo modprobe 88x2bu

```

# Enable CH341 driver for robot controller

```
sudo systemctl stop brltty
sudo systemctl disable brltty
sudo systemctl mask brltty

sudo systemctl stop brltty-udev.service
sudo systemctl disable brltty-udev.service
sudo systemctl mask brltty-udev.service

wget https://github.com/juliagoda/CH341SER/archive/master.zip

# Install build dependencies (if not already done)
sudo apt install build-essential linux-headers-$(uname -r)

# Download and compile CH341 driver
wget https://github.com/juliagoda/CH341SER/archive/master.zip
unzip master.zip
cd CH341SER-master
make
sudo make install
sudo modprobe ch34x

# motor controller
echo 'KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE:="0777", SYMLINK+="myserial"' | sudo tee /etc/udev/rules.d/99-myserial.rules

sudo udevadm control --reload-rules
sudo udevadm trigger


sudo usermod -a -G dialout $USER

````

# Install Pip

```
sudo apt install python3-pip
pip install pyserial
```


# Install jetson-containers

```
# https://github.com/dusty-nv/jetson-containers/blob/master/docs/setup.md

git clone https://github.com/dusty-nv/jetson-containers
bash jetson-containers/install.sh

sudo vi /etc/docker/daemon.json

```

```
{
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    },

    "default-runtime": "nvidia"
}

```

sudo systemctl restart docker


# enable swap

```

sudo systemctl disable nvzramconfig
sudo fallocate -l 16G /mnt/16GB.swap
sudo mkswap /mnt/16GB.swap
sudo swapon /mnt/16GB.swap

```

# Then add the following line to the end of /etc/fstab to make the change persistent:

```
/mnt/16GB.swap  none  swap  sw 0  0

```

# Disable GUI

```
sudo init 3     # stop the desktop
# log your user back into the console (Ctrl+Alt+F1, F2, ect)
sudo init 5     # restart the desktop
```
or
```
$ sudo systemctl set-default multi-user.target     # disable desktop on boot
$ sudo systemctl set-default graphical.target      # enable desktop on boot
```

# Docker Permissions

```
sudo usermod -aG docker $USER
```

# power

```
sudo nvpmodel -q
sudo nvpmodel -m 2 MAXN_SUPER

```

# GPIO - setup

```
pip install Jetson.GPIO --upgrade

git clone git@github.com:kevywilly/jetson-orin-gpio-patch.git
```

```
cd jetson-orin-gpio-patch
dtc -O dtb -o pin7_12_32_33_as_gpio.dtbo pin7_12_32_33_as_gpio.dts
sudo cp pin7_12_32_33_as_gpio.dtbo /boot
sudo /opt/nvidia/jetson-io/jetson-io.py
```

(set csi camera to imx219-c)

(choose overlay for pins 7,12,32,33 as gpio)

