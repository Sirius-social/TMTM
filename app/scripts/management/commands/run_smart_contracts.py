import json
import asyncio
from time import sleep

from django.core.management.base import BaseCommand
from django.conf import settings
from sirius_sdk import Agent, P2PConnection


class Command(BaseCommand):

    help = 'Run Smart-Contracts'
    loop_timeout = 30

    def handle(self, *args, **options):
        if settings.AGENT['entity']:
            print('****** Entity was set, try start Smart-Contracts ******')
            try:
                print('* check agent connection')
                asyncio.get_event_loop().run_until_complete(self.check_agent_connection())
            except Exception as e:
                print('EXCEPTION: check was terminated with exception:')
                print(repr(e))

            print('****** Run listener event-loop ******')
            while True:
                try:
                    asyncio.get_event_loop().run_until_complete(self.run_listener())
                except Exception as e:
                    print('EXCEPTION: exception was raised while process listener event loop. '
                          'Loop will be restarted after %d secs' % self.loop_timeout)
                    print(repr(e))
                    sleep(self.loop_timeout)
        else:
            print('****** Entity is empty, terminate ***********')

    @staticmethod
    async def check_agent_connection():
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
        print('* agent.open()')
        await agent.open()
        try:
            print('* agent.ping()')
            ok = await agent.ping()
            print(f'* ok: {ok}')
            assert ok is True, 'problem with agent p2p'
            print('* agent connection is OK!')
        finally:
            print('* agent.close()')
            await agent.close()

    @staticmethod
    async def run_listener():
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
        await agent.open()
        try:
            print('* agent.subscribe()')
            listener = await agent.subscribe()
            async for event in listener:
                print('* received event: ')
                print('JSON>')
                print(json.dumps(event, indent=4, sort_keys=True))
                print('<')
        finally:
            await agent.close()
