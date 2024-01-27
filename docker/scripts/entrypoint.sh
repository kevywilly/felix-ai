#!/bin/bash
cd /nano-control && sudo /usr/bin/git pull
/etc/init.d/nginx start
cd /felix-ai