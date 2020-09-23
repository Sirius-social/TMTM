from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings

from wrapper.models import UserEntityBind


class Command(BaseCommand):

    help = 'Setup Admin'

    def handle(self, *args, **options):
        if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD and settings.AGENT['entity']:
            user, created = User.objects.get_or_create(username=settings.ADMIN_USERNAME)
            user.set_password(settings.ADMIN_PASSWORD)
            user.is_active = True
            user.is_superuser = True
            user.save()
            bind, _ = UserEntityBind.objects.get_or_create(user=user, entity=settings.AGENT['entity'])
            print('===================================')
            print('ADMIN account was set %s: %s' % (settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD))
            print('===================================')
        else:
            print('===================================')
            print('ADMIN credentials are not set')
            print('===================================')
