from django.db import models
from django.contrib.postgres.fields import JSONField


class Ledger(models.Model):
    name = models.CharField(max_length=512, db_index=True)
    metadata = JSONField(null=True, default=None)

