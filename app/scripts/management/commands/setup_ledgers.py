from datetime import datetime
from django.core.management.base import BaseCommand

from wrapper.models import Ledger, Transaction


class Command(BaseCommand):

    help = 'Setup Ledgers'
    LEDGERS_COUNT = 20
    TXN_COUNT = 5

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
                entity=entity, name='20-001-1000500' + str(ledger_cnt), metadata={'debug': True}
            )
            for txn_cnt in range(self.TXN_COUNT):
                seq_no = txn_cnt + 1
                stamp = datetime.now()
                txn = Transaction.objects.create(
                    ledger=ledger, seq_no=seq_no,
                    txn={
                        'data': txn_cnt
                    },
                    metadata={'seqNo': seq_no, 'txnTime': str(stamp)}
                )
