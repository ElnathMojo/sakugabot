FROM python:3.7

ENV PYTHONUNBUFFERED 1

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg libzbar-dev

RUN mkdir /sakugabot
WORKDIR /sakugabot
ADD requirements.txt /sakugabot/
RUN pip install -r requirements.txt
ADD . /sakugabot/

ENV PYTHONPATH="/sakugabot/:$PYTHONPATH" FFMPEG_BINARY='auto-detect'

