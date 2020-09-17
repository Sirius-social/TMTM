# Generated by Django 2.2 on 2020-09-17 23:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wrapper', '0004_ledger_participants'),
    ]

    operations = [
        migrations.CreateModel(
            name='Content',
            fields=[
                ('id', models.CharField(db_index=True, max_length=128)),
                ('uid', models.CharField(max_length=128, primary_key=True, serialize=False)),
                ('private_uid', models.CharField(db_index=True, max_length=128, unique=True)),
                ('owner', models.CharField(db_index=True, max_length=1024, null=True)),
                ('name', models.CharField(db_index=True, max_length=512)),
                ('content_type', models.CharField(db_index=True, max_length=64, null=True)),
                ('storage', models.CharField(choices=[('django.core.files.storage.FileSystemStorage', 'FileSystemStorage')], db_index=True, default='django.core.files.storage.FileSystemStorage', max_length=256)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated', models.DateTimeField(auto_now=True, null=True)),
                ('is_avatar', models.BooleanField(default=False)),
                ('size_width', models.IntegerField(null=True)),
                ('size_height', models.IntegerField(null=True)),
                ('delete_after_download', models.BooleanField(db_index=True, default=False)),
                ('encoded', models.BooleanField(db_index=True, default=False)),
                ('download_counter', models.IntegerField(db_index=True, default=0)),
            ],
        ),
    ]
