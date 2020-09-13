FROM python:3.8

ARG VERSION='0.0'

ADD app /app
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt && \
    chmod +x /app/wait-for-it.sh

WORKDIR /app

ENV ASGI_PORT=8000
ENV WSGI_PORT=8000

EXPOSE $WSGI_PORT
EXPOSE $ASGI_PORT


HEALTHCHECK --interval=1800s --timeout=3s --start-period=30s \
  CMD curl -f http://localhost:$WSGI_PORT/maintenance/check_health/ || exit 1

# FIRE!!!
CMD echo "Wait database is ready" && /app/wait-for-it.sh ${DATABASE_HOST}:${DATABASE_PORT-5432} --timeout=60 && \
  cd /app && \
  echo "Database migration" && python manage.py migrate && \
  echo "Setup admin" && python manage.py setup_admin && \
  echo "Run server" && (daphne -p $ASGI_PORT -b 0.0.0.0 settings.asgi:application)
