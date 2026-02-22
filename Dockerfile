FROM ubuntu

WORKDIR /app

COPY mqtt-to-email /app
COPY ssmtp.conf /app
RUN apt update && apt install -y ssmtp mosquitto-dev

CMD [ "./mqtt-to-email" ]
