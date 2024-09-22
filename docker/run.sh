sudo jetson-containers run \
-e ROBOT=felixV2 \
--volume /home/orin/projects/felix-ai:/felix-ai \
--device /dev/ttyUSB0 \
--device /dev/myserial \
felix-ai:latest
