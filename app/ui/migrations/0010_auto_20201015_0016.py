# Generated by Django 2.2 on 2020-10-15 00:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui', '0009_pairwiserecord_subscribe'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pairwiserecord',
            name='subscribe',
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]