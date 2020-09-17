import os
import json
import asyncio
from typing import List
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from sirius_sdk import Agent, Pairwise, P2PConnection
from sirius_sdk.agent.consensus import simple as simple_consensus
from sirius_sdk.agent.microledgers import Transaction

from .logger import StreamLogger
from .decorators import sentry_capture_exceptions
from scripts.management.commands import orm


class Command(BaseCommand):

    help = 'Run wrapper transaction'

    def add_arguments(self, parser):
        parser.add_argument('txn_file', type=str)

    def handle(self, *args, **options):
        txn_file = options['txn_file']
        print('-------------------------------')
        print('txn_file: %s' % txn_file)
        print('-------------------------------')
        if os.path.isfile(txn_file):
            txn = json.load(open(txn_file, 'r'))
            typ = txn.get('@type')
            if typ.endswith('create-ledger'):
                ledger = txn.get('name')
                genesis = txn.get('genesis')
                participants = txn.get('participants')
                stream = txn.get('@id')
                time_to_live = txn.get('time_to_live', 30)
                asyncio.get_event_loop().run_until_complete(
                    self.create_new_ledger(
                        name=ledger,
                        genesis=genesis,
                        my_did=settings.AGENT['entity'],
                        participants=participants,
                        stream=stream,
                        time_to_live=time_to_live
                    )
                )
            elif typ.endswith('issue-transaction'):
                pass
            else:
                raise RuntimeError(f'Unexpected @type = {typ}')
        else:
            raise RuntimeError(f'File "{txn_file}" does not exists')

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

    @sentry_capture_exceptions
    async def create_new_ledger(
            self, name: str, genesis: List[dict], my_did: str,
            participants: List[str], stream: str, time_to_live: int = 30
    ):
        """Smart-Contract that implements logic of creating new ledger and replicate new state among
        participants via consensus.

        see details here https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple#step-1-transactions-log-initialization-actor-notify-all-participants-send-propose

        :param name: ledger name
        :param genesis: genesis block with transactions
        :param participants: list of participants who is deal transactions in microledger context
        :param stream: stream id for logger
        :param my_did: DID of self side
        :param time_to_live: ttl of state machine to detect error by timeout
        """
        agent = self.alloc_agent_connection()
        await agent.open()
        try:
            my_verkey = await agent.wallet.did.key_for_local_did(my_did)
            # initialize state-machine
            logger = await StreamLogger.create(stream)
            state_machine = simple_consensus.state_machines.MicroLedgerSimpleConsensus(
                crypto=agent.wallet.crypto,
                me=Pairwise.Me(did=my_did, verkey=my_verkey),
                pairwise_list=agent.pairwise_list,
                microledgers=agent.microledgers,
                transports=agent,
                logger=logger,
                time_to_live=time_to_live
            )
            genesis = [Transaction.create(txn) for txn in genesis]
            tm_start = datetime.utcnow()
            success, new_ledger = await state_machine.init_microledger(
                ledger_name=name,
                participants=participants,
                genesis=genesis
            )
            tm_end = datetime.utcnow()
            delta = (tm_end - tm_start).seconds
            print('operation took %d secs' % delta)
            if success:
                genesis = await new_ledger.get_all_transactions()
                # Store ledger metadata and service info for post-processing and visualize in monitoring service
                await orm.create_ledger(
                    name=new_ledger.name,
                    metadata={
                        'actor': {
                            'label': 'SELF',
                            'did': my_did
                        },
                        'local_timestamp_utc': str(datetime.utcnow()),
                        'participants': participants
                    },
                    genesis=genesis
                )
            else:
                if state_machine.problem_report:
                    explain = state_machine.problem_report.explain
                else:
                    explain = ''
                if await agent.microledgers.is_exists(name):
                    await agent.microledgers.reset(name)
                raise RuntimeError(f'Creation of new ledger was terminated with error: \n"{explain}"')
        finally:
            await agent.close()
