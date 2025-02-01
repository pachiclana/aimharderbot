FROM python:3.12-slim
ENV TZ="Europe/Madrid"

WORKDIR /usr/src/app

COPY src /usr/src/app/src

RUN pip install beautifulsoup4==4.11.0
RUN pip install requests==2.28.0
RUN pip install pyTelegramBotAPI==4.13.0
RUN pip install PyYAML==6.0.2

ENTRYPOINT [ "python3", "./src/main.py"]
