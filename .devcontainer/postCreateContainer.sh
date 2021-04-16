#!/bin/bash

# /bin/echo ------------ postCreateCommand apt-get ------------
# apt-get update
# apt-get -y install bash bluetooth bluez bluez-tools build-essential ca-certificates cython gcc git iputils-ping libatomic1 libavcodec-dev libc-dev libffi-dev libjpeg-dev libpcap-dev libssl-dev make nano openssh-client procps python3 python3-dev python3-dev python3-pip python3-setuptools rfkill unzip wget wget zlib1g-dev

/bin/echo ------------ postCreateCommand python/pip ------------
# /usr/local/bin/python3 -m pip install --upgrade pip
# /usr/local/bin/pip3 install black colorlog debugpy pexpect pygatt pylint PyNaCl==1.3.0
/usr/local/bin/pip3 install -r /workspaces/hacs-govee/requirements_test.txt

# /bin/echo ------------ postCreateCommand container install ------------
# mkdir -p /src/ludeeus
# cd /src/ludeeus
# git clone https://github.com/ludeeus/container
# cp -r ./container/rootfs/common/* /
# chmod +x /usr/bin/container
# /usr/bin/container install

/bin/echo ------------ postCreateCommand symlink our component ------------
# /bin/mkdir -p /config/custom_components
/bin/ln -s /workspaces/hacs-govee/custom_components/govee /config/custom_components/govee

/bin/echo ------------ postCreateCommand install hacs ------------
mkdir -p /src/hacs
cd /src/hacs
/bin/mkdir -p /config/custom_components/hacs
/usr/bin/wget https://github.com/hacs/integration/releases/latest/download/hacs.zip
/usr/bin/unzip hacs.zip -d /config/custom_components/hacs
/bin/rm hacs.zip

/bin/echo ------------ postCreateCommand finished ------------
