#!/usr/bin/env bash
cd /home/nano/projects/felix-ai && ./docker/run.sh felix-ai:latest /felix.sh
journalctl -u felix.service -f
