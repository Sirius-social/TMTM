FROM python:3.8

ARG VERSION='0.0'

ADD app /app
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt && \
    chmod +x /app/wait-for-it.sh

WORKDIR /app

ENV ASGI_PORT=8000

EXPOSE $ASGI_PORT

# FIRE!!!
CMD echo "Wait database is ready" && /app/wait-for-it.sh ${DATABASE_HOST}:${DATABASE_PORT-5432} --timeout=60 && \
  cd /app && \
  echo "Database migration" && python manage.py migrate && \
  echo "Run server" && (daphne -p $ASGI_PORT -b 0.0.0.0 settings.asgi:application)
