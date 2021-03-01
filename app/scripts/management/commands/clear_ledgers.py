import uuid
import random
import asyncio
from datetime import datetime, timedelta

import sirius_sdk
from django.conf import settings
from django.core.management.base import BaseCommand

from wrapper.models import Ledger, Transaction


def get_random_signer():
    verkeys = [value['verkey'] for did, value in settings.PARTICIPANTS_META.items()]
    return random.choice(verkeys)


class Command(BaseCommand):

    help = 'Clear all ledgers'

    async def clear(self):
        agent = sirius_sdk.Agent(
            server_address=settings.AGENT['server_address'],
            credentials=settings.AGENT['credentials'].encode('ascii'),
            p2p=sirius_sdk.P2PConnection(
                my_keys=(
                    settings.AGENT['my_verkey'],
                    settings.AGENT['my_secret_key']
                ),
                their_verkey=settings.AGENT['agent_verkey']
            )
        )
        await agent.open()
        try:
            ledgers = await agent.microledgers.list()
            for ledger in ledgers:
                await agent.microledgers.reset(ledger.name)
                print(f'Ledger "{ledger.name}" was reset')
        finally:
            await agent.close()

    def handle(self, *args, **options):
        if settings.AGENT['entity']:
            asyncio.get_event_loop().run_until_complete(self.clear())
            Ledger.objects.filter(entity=settings.AGENT['entity']).all().delete()
