# Generated by Django 2.2 on 2020-09-15 21:26

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wrapper', '0003_auto_20200912_0957'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledger',
            name='participants',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=128), null=True, size=None),
        ),
    ]
