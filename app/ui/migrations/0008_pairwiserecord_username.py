# Generated by Django 2.2 on 2020-10-10 23:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui', '0007_auto_20201009_2219'),
    ]

    operations = [
        migrations.AddField(
            model_name='pairwiserecord',
            name='username',
            field=models.CharField(db_index=True, max_length=128, null=True),
        ),
    ]
