#!/bin/bash

/bin/echo ------------ postCreateCommand apt-get ------------
apt-get update
apt-get -y install bash bluetooth bluez bluez-tools build-essential ca-certificates cargo cython gcc git iputils-ping libatomic1 libavcodec-dev libc-dev libffi-dev libjpeg-dev libpcap-dev libssl-dev make nano openssh-client procps python3 python3-dev python3-pip python3-setuptools rfkill unzip wget wget zlib1g-dev

/bin/echo ------------ postCreateCommand container install ------------
mkdir -p /src/ludeeus
cd /src/ludeeus
git clone https://github.com/ludeeus/container
cp -r ./container/rootfs/common/* /
chmod +x /usr/bin/container
/usr/bin/container install

/workspaces/hacs-govee/.devcontainer/postHassUpdated.sh

/bin/echo ------------ postCreateCommand finished ------------
