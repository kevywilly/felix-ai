#!/bin/bash
echo "starting trainer"
nohup python3 -m felix.train &
echo "finished training"
