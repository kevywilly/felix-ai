#!/usr/bin/env bash
cd /nano-control && /usr/bin/git pull
/etc/init.d/nginx start
cd /felix-ai