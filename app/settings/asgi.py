import os
import importlib

import django
from django.conf import settings


def get_application(app_path: str):
    path, name = app_path.rsplit(".", 1)
    module = importlib.import_module(path)
    value = getattr(module, name)
    return value


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.production")
django.setup()

application = get_application(settings.ASGI_APPLICATION)
