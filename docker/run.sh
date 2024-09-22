sudo jetson-containers run \
-e ROBOT=felixV2 \
--volume /home/orin/felix-ai:/felix-ai \
--device /dev/ttyAMA0 \
felix-ai:latest
