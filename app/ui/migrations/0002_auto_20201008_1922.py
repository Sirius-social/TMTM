# Generated by Django 2.2 on 2020-10-08 19:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='qrcode',
            name='url',
            field=models.CharField(db_index=True, max_length=2048),
        ),
    ]