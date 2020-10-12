import asyncio
from django.core.management.base import BaseCommand
from channels.db import database_sync_to_async

from .run_smart_contracts import parse_and_store_gu


class Command(BaseCommand):

    help = 'Test GU-11 & GU-12'

    def handle(self, *args, **options):
        asyncio.get_event_loop().run_until_complete(self.routine())

    async def routine(self):
        txn = {
          "@type": "https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/gu-12",
          "@id": "1129fbc9-b9cf-4191-b5c1-ee9c68945f42",
          "no": "100000-03",
          "date": "01/01/2020",
          "cargo_name": "Сборный контейнер",
          "depart_station": "Karagandi",
          "arrival_station": "Poti",
          "month": "Май",
          "year": "2020",
          "tonnage": "10",
          "shipper": "ООО ТревелСейл",
          "~attach": [
             {
                "@id": "document-1",
                "mime_type": "application/pdf",
                "filename": "WayBill_xxx_yyy_zzz.pdf",
                "data": {
                  "json": {
                    "url": "https://wsfvqewf.pdf",
                    "md5": "xxxx"
                  }
                }
             },
             {
                "@id": "document-2",
                "mime_type": "image/png",
                "filename": "WayBill_xxx_yyy_zzz_attaches.png",
                "data": {
                  "json": {
                    "url": "https://wsfvqewf.png",
                    "md5": "zzz"
                  }
                }
             }
          ]
        }
        await database_sync_to_async(parse_and_store_gu)(txn, 'gu11')
