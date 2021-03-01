import uuid
import random
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from wrapper.models import Ledger, Transaction


def get_random_signer():
    verkeys = [value['verkey'] for did, value in settings.PARTICIPANTS_META.items()]
    return random.choice(verkeys)


class Command(BaseCommand):

    help = 'Setup Ledgers'
    LEDGERS_COUNT = 20
    TXN_COUNT = 30

    def add_arguments(self, parser):
        parser.add_argument('entity', type=str)

    def handle(self, *args, **options):
        entity = options['entity']
        print('-------------------------------')
        print('Entity: %s' % entity)
        print('-------------------------------')
        Ledger.objects.filter(entity=entity).all().delete()
        for ledger_cnt in range(self.LEDGERS_COUNT):
            ledger = Ledger.objects.create(
                entity=entity, name='Container-' + str(ledger_cnt), metadata={'debug': True}
            )
            today = datetime.today()
            start_date = today - timedelta(days=self.TXN_COUNT+3)
            for txn_cnt in range(self.TXN_COUNT):
                seq_no = txn_cnt + 1
                date = start_date + timedelta(days=seq_no)
                date = '%2d.%2d.%2d' % (date.day, date.month, date.year)
                date = date.replace(' ', '0')
                stamp = datetime.now()
                txn = Transaction.objects.create(
                    ledger=ledger, seq_no=seq_no,
                    txn={
                        "@type": "https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/issue-transaction",
                        "@id": uuid.uuid4().hex,
                        "no": "20-001-0000002-" + str(seq_no),
                        "date": date,
                        "cargo": "Kids toys",
                        "departure_station": "Караганда",
                        "arrival_station": "Актау",
                        "doc_type": "WayBill",
                        "ledger": {
                           "name": ledger.name
                        },
                        "waybill": {
                           "no": "xxx-yyy",
                           "wagon_no": "WSG-XXX-YYY"
                        },
                        "~attach": [
                           {
                              "@id": "document-1",
                              "mime_type": "application/pdf",
                              "filename": "WayBill_xxx_yyy_zzz.pdf",
                              "data": {
                                "json": {
                                  "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                                  "md5": "eaa13b3aa037b874d7835514b2a02514"
                                }
                              }
                           },
                           {
                              "@id": "document-2",
                              "mime_type": "application/doc",
                              "filename": "WayBill_xxx_yyy_zzz_attaches.doc",
                              "data": {
                                "json": {
                                  "url": "https://www.sample-videos.com/doc/Sample-doc-file-200kb.doc",
                                  "md5": "eaa13b3aa037b874d7835514b2a02514"
                                }
                              }
                           }
                        ],
                        "time_to_live": 15,
                        "msg~sig": {
                            "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/signature/1.0/ed25519Sha512_single",
                            "signature": "_Oh48kK9I_QNiBRJfU-_HPAUxyIcrn3Ba8QwspSqiy8AMLMN4h8vbozImSr2dnVS2RaOfimWDgWVtZCTvbdjBQ==",
                            "signer": get_random_signer()
                        }
                    },
                    metadata={'seqNo': seq_no, 'txnTime': str(stamp)}
                )
