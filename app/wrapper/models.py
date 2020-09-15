from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField


class Ledger(models.Model):
    entity = models.CharField(max_length=64, db_index=True, null=True)
    name = models.CharField(max_length=512, db_index=True)
    metadata = JSONField(null=True, default=None)
    participants = ArrayField(models.CharField(max_length=128), null=True)

    class Meta:
        unique_together = ('entity', 'name')


class Transaction(models.Model):
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    txn = JSONField()
    seq_no = models.IntegerField(null=True)
    metadata = JSONField(null=True, default=None)

    class Meta:
        unique_together = ('seq_no', 'ledger')
