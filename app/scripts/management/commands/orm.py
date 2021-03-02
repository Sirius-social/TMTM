from typing import List

from django.db.transaction import atomic
from django.conf import settings
from channels.db import database_sync_to_async

from wrapper.models import Ledger, Transaction


async def create_ledger(name: str, metadata: dict, genesis: List[dict]) -> int:

    def sync(name_: str, metadata_: dict, genesis_: List[dict]) -> int:
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
            return ledger.id

    return await database_sync_to_async(sync)(name, metadata, genesis)


async def reset_ledger(name: str):

    def sync(name_: str):
        Ledger.objects.filter(name=name_, entity=settings.AGENT['entity']).all().delete()

    await database_sync_to_async(sync)(name)


async def store_transactions(ledger: str, transactions: List[dict], their_did: str = None):

    def sync(ledger_: str, transactions_: List[dict]):
        ledger_model = Ledger.objects.get(name=ledger_, entity=settings.AGENT['entity'])
        with atomic():
            for txn in transactions_:
                m = txn.pop('txnMetadata')
                t = Transaction.objects.create(
                    ledger=ledger_model,
                    txn=txn,
                    seq_no=m.get('seqNo'),
                    metadata=m,
                    actor_entity=their_did
                )

    await database_sync_to_async(sync)(ledger, transactions)
