from functools import wraps

from sentry_sdk import capture_exception


def sentry_capture_exceptions(f):
    @wraps(f)
    async def wrapped(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except Exception as e:
            print('============== EXCEPTION ===============')
            print(repr(e))
            print('========================================')
            capture_exception(e)
    return wrapped
