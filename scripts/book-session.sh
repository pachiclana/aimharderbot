#!/bin/bash
cd /home/pi/aimharderbot

#We run the docker container and book the session according to the parameters
docker run --rm -v $(pwd)/logs:/usr/src/app/logs \
				-v $(pwd)/config:/usr/src/app/config \
    			--name aimharderbot aimharderbot:v1 \
				--config-filename='aimharderbot_config.yaml'
