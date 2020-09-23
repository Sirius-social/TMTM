import json
import logging
import asyncio
from time import sleep
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from sirius_sdk import Agent, P2PConnection, Pairwise
from sirius_sdk.agent.listener import Event
from sirius_sdk.errors.exceptions import SiriusConnectionClosed
from sirius_sdk.errors.indy_exceptions import WalletItemAlreadyExists
from sirius_sdk.agent.consensus import simple as simple_consensus

from scripts.management.commands import orm
from scripts.management.commands.decorators import sentry_capture_exceptions
from scripts.management.commands.logger import StreamLogger
from wrapper.utils import get_auth_connection_key_seed


class Command(BaseCommand):

    help = 'Run Smart-Contracts'
    loop_timeout = 30
    test_ledger_prefix = 'test_'

    def handle(self, *args, **options):
        if settings.AGENT['entity']:
            logging.error('****** Entity was set, try start Smart-Contracts ******')
            try:
                logging.error('* check agent connection')
                asyncio.get_event_loop().run_until_complete(self.check_agent_connection())
            except Exception as e:
                logging.error('EXCEPTION: check was terminated with exception:')
                logging.error(repr(e))

            try:
                logging.error('* clean test ledgers')
                asyncio.get_event_loop().run_until_complete(self.clean_test_ledgers())
            except Exception as e:
                logging.error('EXCEPTION: check was terminated with exception:')
                logging.error(repr(e))

            try:
                logging.error('* init connection invitations')
                asyncio.get_event_loop().run_until_complete(self.init_connect_invitations())
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

    async def clean_test_ledgers(self):
        agent = self.alloc_agent_connection()
        await agent.open()
        try:
            ledgers = await agent.microledgers.list()
            logging.error('* ledgers count: %d' % len(ledgers))
            test_ledgers = [ledger for ledger in ledgers if ledger['name'].lower().startswith(self.test_ledger_prefix)]
            logging.error('* test ledgers count: %d' % len(test_ledgers))
            for name in [ledger['name'] for ledger in test_ledgers]:
                try:
                    await agent.microledgers.reset(name)
                    await orm.reset_ledger(name)
                except Exception as e:
                    logging.error('* exception raised while reset ledger [%s]' % name)
                    logging.error(repr(e))
            ledgers = await agent.microledgers.list()
            logging.error('* after cleaning ledgers count: %d' % len(ledgers))
        finally:
            await agent.close()

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

    async def init_connect_invitations(self):
        agent = self.alloc_agent_connection()
        logging.error('* agent.open()')
        await agent.open()
        try:
            seed_auth_key = get_auth_connection_key_seed()
            try:
                # Ensure key exists
                await agent.wallet.crypto.create_key(seed=seed_auth_key)
            except WalletItemAlreadyExists:
                pass
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

                if event.pairwise:
                    logging.error('* event.pairwise is filled')
                    if isinstance(event.message, simple_consensus.messages.InitRequestLedgerMessage):
                        logging.error('* init_ledger_accepting')
                        fut = self.init_ledger_accepting(
                            propose=event.message,
                            p2p=event.pairwise
                        )
                        asyncio.ensure_future(fut)
                    elif isinstance(event.message, simple_consensus.messages.ProposeTransactionsMessage):
                        logging.error('* accept_transactions')
                        fut = self.accept_transactions(
                            propose=event.message,
                            p2p=event.pairwise
                        )
                        asyncio.ensure_future(fut)
        finally:
            await agent.close()

    @sentry_capture_exceptions
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
            logger = await StreamLogger.create('ledgers')
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

    @sentry_capture_exceptions
    async def accept_transactions(self, propose: simple_consensus.messages.ProposeTransactionsMessage, p2p: Pairwise):
        """Smart-Contract that implements logic of accepting for new transactions batches.

        :param propose: propose message,
            see details here https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple#stage-1-propose-transactions-block-stage-propose
        :param p2p: pairwise that was established earlier statically or via Aries 0160 protocol https://github.com/hyperledger/aries-rfcs/tree/master/features/0160-connection-protocol
        """
        # allocate connection to Agent services
        agent = self.alloc_agent_connection()
        await agent.open()
        try:
            # initialize state-machine
            logger = await StreamLogger.create('transactions')
            state_machine = simple_consensus.state_machines.MicroLedgerSimpleConsensus(
                crypto=agent.wallet.crypto,
                me=p2p.me,
                pairwise_list=agent.pairwise_list,
                microledgers=agent.microledgers,
                transports=agent,
                logger=logger
            )
            # Run state-machine. State progress is described here:
            # https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple#use-case-2-accept-transaction-to-existing-ledger-by-all-dealers-in-microledger-space
            success = await state_machine.accept_commit(
                actor=p2p,
                propose=propose
            )
            if success:
                await orm.store_transactions(
                    ledger=propose.state.name,
                    transactions=propose.transactions
                )
            else:
                if state_machine.problem_report:
                    explain = state_machine.problem_report.explain
                else:
                    explain = ''
                raise RuntimeError(f'Accepting of new transactions was terminated with error: \n"{explain}"')
        finally:
            await agent.close()
