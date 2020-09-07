from django.db import models
from django.contrib.postgres.fields import JSONField


class Ledger(models.Model):
    name = models.CharField(max_length=512, db_index=True)
    metadata = JSONField(null=True, default=None)


class Transaction(models.Model):
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    txn = JSONField()
    metadata = JSONField(null=True, default=None)
