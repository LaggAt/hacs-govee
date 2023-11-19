#!/bin/bash

/bin/echo ------------ postCreateCommand apt-get ------------
#TODO: remove unused
apt-get update
apt-get -y install bash bluetooth bluez bluez-tools build-essential ca-certificates cargo cython gcc git iputils-ping libatomic1 libavcodec-dev libc-dev libffi-dev libjpeg-dev libpcap-dev libssl-dev make nano openssh-client procps python3 python3-dev python3-pip python3-setuptools rfkill unzip wget wget zlib1g-dev

#activate all custom_components in /workspaces/...
/usr/local/bin/dev component activate --all

# install dependencies



#start home assistant in background
/usr/local/bin/dev ha start &

#/bin/echo ------------ postCreateCommand finished ------------
