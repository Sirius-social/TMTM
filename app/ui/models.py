from django.db import models
from django.contrib.postgres.fields import JSONField


class QRCode(models.Model):
    connection_key = models.CharField(max_length=64, db_index=True)
    my_endpoint = JSONField(null=True)
    url = models.CharField(max_length=2048, db_index=True)


class PairwiseRecord(models.Model):
    entity = models.CharField(max_length=64)
    their_did = models.CharField(max_length=64, db_index=True)
    metadata = JSONField()
