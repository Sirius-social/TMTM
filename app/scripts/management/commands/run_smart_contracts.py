import json
import logging
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
            logging.error('****** Entity was set, try start Smart-Contracts ******')
            try:
                logging.error('* check agent connection')
                asyncio.get_event_loop().run_until_complete(self.check_agent_connection())
            except Exception as e:
                logging.error('EXCEPTION: check was terminated with exception:')
                logging.error(repr(e))

            logging.error('****** Run listener event-loop ******')
            while True:
                try:
                    asyncio.get_event_loop().run_until_complete(self.run_listener())
                except Exception as e:
                    logging.error('EXCEPTION: exception was raised while process listener event loop. '
                          'Loop will be restarted after %d secs' % self.loop_timeout)
                    logging.error(repr(e))
                    sleep(self.loop_timeout)
        else:
            logging.error('****** Entity is empty, terminate ***********')

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
        logging.error('* agent.open()')
        await agent.open()
        try:
            logging.error('* agent.ping()')
            ok = await agent.ping()
            logging.error(f'* ok: {ok}')
            assert ok is True, 'problem with agent p2p'
            logging.error('* agent connection is OK!')
            logging.error('* find entity in wallet')
            _ = await agent.wallet.did.get_my_did_with_meta(settings.AGENT['entity'])
            logging.error('* entity was found')
        finally:
            logging.error('* agent.close()')
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
            logging.error('* agent.subscribe()')
            listener = await agent.subscribe()
            async for event in listener:
                logging.error('* received event: ')
                logging.error('JSON>')
                logging.error(json.dumps(event, indent=4, sort_keys=True))
                logging.error('<')
        finally:
            await agent.close()
