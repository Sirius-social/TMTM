import os
import hashlib
import secrets

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField, ArrayField


def import_class(name):
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


class UserEntityBind(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='entities')
    entity = models.CharField(max_length=64)

    class Meta:
        unique_together = ('entity', 'user')


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


class GURecord(models.Model):
    entity = models.CharField(max_length=64, db_index=True)
    category = models.CharField(max_length=36, db_index=True)
    no = models.CharField(max_length=128)
    date = models.CharField(max_length=128)
    cargo_name = models.CharField(max_length=128)
    depart_station = models.CharField(max_length=128)
    arrival_station = models.CharField(max_length=128)
    month = models.CharField(max_length=128)
    year = models.CharField(max_length=128)
    decade = models.CharField(max_length=128)
    tonnage = models.CharField(max_length=128)
    shipper = models.CharField(max_length=128)
    attachments = JSONField()


class Content(models.Model):

    STORAGE_FILE_SYSTEM = 'django.core.files.storage.FileSystemStorage'
    SUPPORTED_STORAGE = [
        (STORAGE_FILE_SYSTEM, 'FileSystemStorage'),
    ]

    id = models.CharField(max_length=128, db_index=True)
    uid = models.CharField(max_length=128, primary_key=True)
    entity = models.CharField(max_length=1024, null=True, db_index=True)
    name = models.CharField(max_length=512, db_index=True)
    content_type = models.CharField(max_length=1024, null=True, db_index=True)
    storage = models.CharField(max_length=256, db_index=True, choices=SUPPORTED_STORAGE, default=STORAGE_FILE_SYSTEM)
    created = models.DateTimeField(null=True, auto_now_add=True)
    updated = models.DateTimeField(null=True, auto_now=True)
    is_avatar = models.BooleanField(default=False)
    size_width = models.IntegerField(null=True)
    size_height = models.IntegerField(null=True)
    delete_after_download = models.BooleanField(default=False, db_index=True)
    encoded = models.BooleanField(default=False, db_index=True)
    download_counter = models.IntegerField(default=0, db_index=True)
    md5 = models.CharField(max_length=128, null=True)

    @property
    def url(self):
        return settings.MEDIA_URL + self.uid

    def get_storage_instance(self):
        cls = import_class(self.storage)
        return cls()

    def set_file(self, file):
        self.name = file.name
        self.content_type = file.content_type
        _, ext = os.path.splitext(file.name.lower())
        self.id = secrets.token_hex(16)
        self.uid = self.id + ext
        self.get_storage_instance().save(self.uid, file)
        file.seek(0)
        content = file.read()
        self.md5 = hashlib.md5(content).hexdigest()
        self.entity = settings.AGENT['entity']
        pass

    def delete(self, using=None, keep_parents=False):
        try:
            self.get_storage_instance().delete(self.uid)
        except NotImplementedError:
            pass
        super().delete(using, keep_parents)


class Token(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    value = models.CharField(max_length=128, db_index=True)
    entity = models.CharField(max_length=1024, db_index=True)

    @staticmethod
    def allocate(user: User):
        inst = Token.objects.create(
            user=user,
            value=secrets.token_hex(16),
            entity=settings.AGENT['entity']
        )
        return inst
