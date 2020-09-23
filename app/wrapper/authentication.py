from rest_framework.authentication import BasicAuthentication as DefaultBasicAuthentication
from rest_framework import exceptions
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class ExtendedBasicAuthentication(DefaultBasicAuthentication):

    def authenticate_credentials(self, userid, password, request=None):
        user = User.objects.filter(
            username=userid,
            entities__entity=settings.AGENT['entity']
        ).first()

        if user and not user.check_password(password):
            user = None

        if user is None:
            raise exceptions.AuthenticationFailed(_('Invalid username/password.'))

        if not user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))

        return user, None
