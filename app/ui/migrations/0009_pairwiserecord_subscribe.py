# Generated by Django 2.2 on 2020-10-14 23:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui', '0008_pairwiserecord_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='pairwiserecord',
            name='subscribe',
            field=models.BooleanField(default=True),
        ),
    ]