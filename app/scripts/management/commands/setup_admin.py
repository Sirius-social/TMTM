from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):

    help = 'Setup Admin'

    def handle(self, *args, **options):
        if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD:
            user, created = User.objects.get_or_create(username=settings.ADMIN_USERNAME)
            user.set_password(settings.ADMIN_PASSWORD)
            user.save()
            print('===================================')
            print('ADMIN account was set %s: %s' % (settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD))
            print('===================================')
        else:
            print('===================================')
            print('ADMIN credentials are not set')
            print('===================================')
