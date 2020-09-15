import json
import logging
import asyncio
from time import sleep
from datetime import datetime

import aioredis
from django.core.management.base import BaseCommand
from django.conf import settings
from sirius_sdk import Agent, P2PConnection, Pairwise
from sirius_sdk.agent.listener import Event
from sirius_sdk.errors.exceptions import SiriusConnectionClosed
from sirius_sdk.agent.consensus import simple as simple_consensus

from scripts.management.commands import orm


class StreamLogger:

    def __init__(self, stream: str):
        self.__redis = None
        self.__stream = stream
        self.__channel_name = settings.AGENT['entity']

    @staticmethod
    async def create():
        inst = StreamLogger()
        if settings.REDIS:
            inst.__redis = await aioredis.create_redis('redis://%s' % settings.REDIS, timeout=3)
        return inst

    async def __call__(self, *args, **kwargs):
        event = dict(
            stream=self.__stream,
            payload=dict(**kwargs)
        )
        event_str = json.dumps(event, sort_keys=True, indent=4)
        logging.error('============== LOG =============')
        logging.error(event_str)
        logging.error('================================')
        if self.__redis:
            await self.__redis.publish(event_str)


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
                    if isinstance(e, SiriusConnectionClosed):
                        logging.error('Agent connection is finished, re-enter loop')
                        sleep(1)
                    else:
                        logging.error(
                            'EXCEPTION: exception was raised while process listener event loop. '
                            'Loop will be restarted after %d secs' % self.loop_timeout
                        )
                        logging.error(repr(e))
                        sleep(self.loop_timeout)
        else:
            logging.error('****** Entity is empty, terminate ***********')

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

    async def check_agent_connection(self):
        agent = self.alloc_agent_connection()
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

    async def run_listener(self):
        agent = self.alloc_agent_connection()
        await agent.open()
        try:
            logging.error('* agent.subscribe()')
            listener = await agent.subscribe()
            async for event in listener:
                logging.error('* received event: ')
                logging.error('JSON>')
                logging.error(json.dumps(event, indent=4, sort_keys=True))
                logging.error('<')

                assert isinstance(event, Event)

                if isinstance(event.message, simple_consensus.messages.InitRequestLedgerMessage) and event.pairwise:
                    logging.error('')
        finally:
            await agent.close()

    async def init_ledger_accepting(self, propose: simple_consensus.messages.InitRequestLedgerMessage, p2p: Pairwise):
        """Smart-Contract that implements logic of new ledger accepting.

        :param propose: propose message,
            see details here https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple#step-1-transactions-log-initialization-actor-notify-all-participants-send-propose
        :param p2p: pairwise that was established earlier statically or via Aries 0160 protocol https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol
        """
        # allocate connection to Agent services
        agent = self.alloc_agent_connection()
        await agent.open()
        try:
            # initialize state-machine
            logger = await StreamLogger.create()
            state_machine = simple_consensus.state_machines.MicroLedgerSimpleConsensus(
                crypto=agent.wallet.crypto,
                me=p2p.me,
                pairwise_list=agent.pairwise_list,
                microledgers=agent.microledgers,
                transports=agent,
                logger=logger
            )
            # Run state-machine. State progress is described here:
            # https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple#use-case-1-creating-new-ledger
            success, new_ledger = await state_machine.accept_microledger(
                actor=p2p,
                propose=propose
            )
            if success:
                genesis = await new_ledger.get_all_transactions()
                # Store ledger metadata and service info for post-processing and visualize in monitoring service
                await orm.create_ledger(
                    name=new_ledger.name,
                    metadata={
                        'actor': {
                            'label': p2p.their.label,
                            'did': p2p.their.did
                        },
                        'local_timestamp_utc': str(datetime.utcnow()),
                        'participants': propose.participants
                    },
                    genesis=genesis
                )
            else:
                if state_machine.problem_report:
                    explain = state_machine.problem_report.explain
                else:
                    explain = ''
                raise RuntimeError(f'Creation of new ledger was terminated with error: \n"{explain}"')
        finally:
            await agent.close()

