#!/bin/bash
cd ~/jetson-containers && ./build.sh --name=ai-base pytorch pycuda cupy gstreamer torchvision torchaudio tensorflow2 transformers
