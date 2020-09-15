import asyncio
from django.core.management.base import BaseCommand
from datetime import datetime

from .orm import create_ledger, reset_ledger, store_transactions
from .run_smart_contracts import Command as ExtCommand


class Command(BaseCommand):

    help = 'Test ORM'
    LEDGER_NAME = 'test_ledger'

    def handle(self, *args, **options):
        asyncio.get_event_loop().run_until_complete(self.routine())

    async def routine(self):
        agent = ExtCommand.alloc_agent_connection()
        await agent.open()
        try:
            is_ledger_exists = await agent.microledgers.is_exists(self.LEDGER_NAME)
            if is_ledger_exists:
                await agent.microledgers.reset(self.LEDGER_NAME)
                await reset_ledger(self.LEDGER_NAME)
            genesis = [
                {'reqID': 'qwewerqwrqw', 'op': 'Op1'},
                {'reqID': '23433254232', 'op': 'Op2'}
            ]
            new_ledger, txns = await agent.microledgers.create(self.LEDGER_NAME, genesis)
            txns = await new_ledger.get_all_transactions()
            print('%')
            await create_ledger(
                name=new_ledger.name,
                metadata={
                    'actor': {
                        'label': 'Test',
                        'did': 'Fake-DID'
                    },
                    'local_timestamp_utc': str(datetime.utcnow()),
                    'participants': ['P1', 'P2']
                },
                genesis=txns
            )
            print('$')

            new_txns = [
                {'reqID': '23423432', 'op': 'Op3'},
                {'reqID': 'werwerewr', 'op': 'Op4'},
                {'reqID': 'gsgsggsegseg', 'op': 'Op5'},
                {'reqID': 'kuyktyjrtjrtj', 'op': 'Op6'}
            ]
            start, end, txns = await new_ledger.append(
                transactions=new_txns,
                txn_time=str(datetime.utcnow())
            )
            print('&')
            await store_transactions(self.LEDGER_NAME, txns)
            print('=')
        finally:
            await agent.close()
