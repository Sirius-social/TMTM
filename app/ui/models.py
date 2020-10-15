from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField


class QRCode(models.Model):
    connection_key = models.CharField(max_length=64, db_index=True)
    my_endpoint = JSONField(null=True)
    url = models.CharField(max_length=2048, db_index=True)


class PairwiseRecord(models.Model):
    entity = models.CharField(max_length=64)
    their_did = models.CharField(max_length=64, db_index=True)
    metadata = JSONField()
    username = models.CharField(max_length=128, null=True, db_index=True)
    subscribe = models.BooleanField(default=True, db_index=True)


class AuthRef(models.Model):
    uid = models.CharField(max_length=1024, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_refs')
    created_at = models.DateTimeField(auto_now_add=True)


class CredentialQR(models.Model):
    username = models.CharField(max_length=126, db_index=True)
    qr = models.OneToOneField(QRCode, on_delete=models.CASCADE, null=True)
