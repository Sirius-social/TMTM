import asyncio

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.conf import settings
from sirius_sdk import Agent, P2PConnection


class Command(BaseCommand):

    help = 'Create new Entity'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=str)

    def handle(self, *args, **options):
        seed = options.get('seed')
        try:
            did, verkey = asyncio.get_event_loop().run_until_complete(self.create_entity(seed))
            print('================= NEW ENTITY ===================')
            print('ENTITY:\t' + did)
            print('VERKEY:\t' + verkey)
            print('================================================')
        except Exception as e:
            print('ERROR: ' + str(e))

    @classmethod
    async def create_entity(cls, seed: str = None):
        agent = cls.alloc_agent_connection()
        await agent.open()
        try:
            did, verkey = await agent.wallet.did.create_and_store_my_did(seed=seed)
            return did, verkey
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
