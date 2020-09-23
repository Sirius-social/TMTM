import hashlib

from django.conf import settings


def get_auth_connection_key_seed() -> str:
    auth_key = "%s:auth" % str(settings.AGENT['entity'])
    seed_auth_key = hashlib.md5(auth_key.encode()).hexdigest()
    return seed_auth_key
