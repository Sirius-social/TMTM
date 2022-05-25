import asyncio
import json

from django.core.management.base import BaseCommand
from channels.db import database_sync_to_async

from django.conf import settings
from sirius_sdk import Agent, P2PConnection, Pairwise


class Command(BaseCommand):

    help = 'Test Agent Entity'

    def handle(self, *args, **options):
        asyncio.get_event_loop().run_until_complete(self.run())

    async def run(self):
        agent = self.alloc_agent_connection()
        await agent.open()
        try:
            my_did = settings.AGENT['entity']
            meta = await agent.wallet.did.get_my_did_with_meta(my_did)
            print(f'\nMetadata for DID[{my_did}]:\n')
            print(json.dumps(meta, indent=2, sort_keys=True))
            pairwises = await agent.wallet.pairwise.list_pairwise()
            print('\nPairwises:\n')
            for pw in pairwises:
                print(json.dumps({'my_did': pw['my_did'], 'their_did': pw['their_did']}, indent=2, sort_keys=True))
        finally:
            await agent.close()

    @staticmethod
    def alloc_agent_connection() -> Agent:
        agent = Agent(
            server_address=settings.AGENT['server_address'],
            credentials=settings.AGENT['credentials'].encode('ascii'),
            p2p=P2PConnection(
                my_keys=(
                    settings.AGENT['my_verkey'],
                    settings.AGENT['my_secret_key']
                ),
                their_verkey=settings.AGENT['agent_verkey']
            )
        )
        return agent
