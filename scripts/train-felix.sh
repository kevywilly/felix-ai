#!/usr/bin/env bash
cd /home/orin/felix-ai && ./docker/run.sh felix-ai:latest /train.sh
journalctl -u felix.service -f
