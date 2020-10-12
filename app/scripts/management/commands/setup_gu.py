import uuid
import random
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from wrapper.models import GURecord


class Command(BaseCommand):

    help = 'Setup GU-11 & GU-12 records'
    TXN_COUNT = 10

    def add_arguments(self, parser):
        parser.add_argument('entity', type=str)

    def handle(self, *args, **options):
        entity = options['entity']
        GURecord.objects.filter(entity=entity).all().delete()
        for category in ['gu11', 'gu12']:
            for no in range(self.TXN_COUNT):
                record = GURecord.objects.create(
                    entity=entity, category=category, no=f'no-{no}', date=str(datetime.utcnow()),
                    cargo_name='Tomato', depart_station='Depart', arrival_station='Arrival',
                    month=random.choice(['nov', 'sep', 'aug', 'jan']),
                    year='2020', decade=random.choice(['1', '2', '3']),
                    tonnage=f'{no}', shipper='Shipper', attachments=[]
                )
