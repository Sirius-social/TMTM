from django.db import models


class QRCode(models.Model):
    connection_key = models.CharField(max_length=64, db_index=True)
    url = models.CharField(max_length=2048)
