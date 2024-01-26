#!/bin/bash
cd ~/jetson-containers && ./build.sh --name=ai-base pytorch:1.10 pycuda cupy gstreamer torchvision torchaudio tensorflow2 transformers
