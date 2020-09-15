from typing import List

from django.db.transaction import atomic
from django.conf import settings
from channels.db import database_sync_to_async

from wrapper.models import Ledger, Transaction


async def create_ledger(name: str, metadata: dict, genesis: List[dict]):

    def sync(name_: str, metadata_: dict, genesis_: List[dict]):
        with atomic():
            ledger = Ledger.objects.create(
                name=name_,
                metadata=metadata_,
                entity=settings.AGENT['entity'],
            )
            with atomic():
                for txn in genesis_:
                    m = txn.pop('txnMetadata')
                    t = Transaction.objects.create(
                        ledger=ledger,
                        txn=txn,
                        seq_no=m.get('seqNo'),
                        metadata=m
                    )

    await database_sync_to_async(sync)(name, metadata, genesis)
