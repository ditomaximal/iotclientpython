#!/bin/bash
# navigate to home directory, then to this directory, then execute python script, then back home

# option: switch on ppp
# ppp-on if peer file is named provider
# ifup gprs
#
sleep 10
cd /home/pi/iotclient/iotclient
sudo python3 iotclient.py 
cd /
