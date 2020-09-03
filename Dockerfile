FROM python:3.8

ARG VERSION='0.0'

ADD app /app
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

WORKDIR /app
