import json
import uuid
from typing import Optional
from datetime import datetime
from typing import List, Dict
from contextlib import asynccontextmanager
from django.conf import settings
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from sirius_sdk import Agent, P2PConnection, Pairwise
from sirius_sdk.agent.consensus import simple
from sirius_sdk.agent.microledgers import Transaction
from sirius_sdk.errors.exceptions import SiriusPromiseContextException
from sirius_sdk.agent.aries_rfc.utils import sign
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol import Invitation

from scripts.management.commands.decorators import sentry_capture_exceptions
from scripts.management.commands.logger import StreamLogger
from scripts.management.commands import orm

from .models import Token


REQUEST_ERROR = 'request_error'
REQUEST_PROCESSING_ERROR = 'request_processing_error'


async def load_token(value: str) -> Optional[Token]:

    def sync(value_: str) -> Optional[Token]:
        return Token.objects.filter(entity=settings.AGENT['entity'], value=value).first()

    return await database_sync_to_async(sync)(value)


def build_problem_report(problem_code: str, explain: str) -> dict:
    report = {
        "@type": "https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/problem_report",
        "@id": uuid.uuid4().hex,
        "problem-code": problem_code,
        "explain": explain
    }
    return report


def build_progress_report(progress: float, message: str, done: bool=False) -> dict:
    msg = {
        "@type": "https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/progress",
        "@id": uuid.uuid4().hex,
        "progress": progress,
        "message": message,
        "done": done
    }
    return msg


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


@asynccontextmanager
async def get_connection():
    agent = alloc_agent_connection()
    await agent.open()
    try:
        yield agent
    finally:
        await agent.close()


async def create_new_ledger(
        my_did: str, name: str, genesis: List[Transaction], ttl: int, stream_id: str, handler=None
) -> int:
    async with get_connection() as agent:
        my_verkey = await agent.wallet.did.key_for_local_did(my_did)
        logger = await StreamLogger.create(stream=stream_id, cb=handler)
        state_machine = simple.state_machines.MicroLedgerSimpleConsensus(
            crypto=agent.wallet.crypto,
            me=Pairwise.Me(my_did, my_verkey),
            pairwise_list=agent.pairwise_list,
            microledgers=agent.microledgers,
            transports=agent,
            logger=logger,
            time_to_live=ttl
        )
        # Add signature to transactions
        signed_genesis = []
        for txn in genesis:
            if 'msg~sig' in txn:
                del txn['msg~sig']
            signature = await sign(agent.wallet.crypto, dict(txn), my_verkey)
            del signature['sig_data']
            txn['msg~sig'] = signature
            signed_genesis.append(Transaction.create(txn))
        success, new_ledger = await state_machine.init_microledger(
            ledger_name=name,
            participants=settings.PARTICIPANTS,
            genesis=signed_genesis
        )
        if success:
            genesis = await new_ledger.get_all_transactions()
            # Store ledger metadata and service info for post-processing and visualize in monitoring service
            ledger_id = await orm.create_ledger(
                name=new_ledger.name,
                metadata={
                    'actor': {
                        'label': 'SELF',
                        'did': my_did
                    },
                    'local_timestamp_utc': str(datetime.utcnow()),
                    'participants': settings.PARTICIPANTS
                },
                genesis=genesis
            )
            return ledger_id
        else:
            if state_machine.problem_report:
                explain = state_machine.problem_report.explain
            else:
                explain = ''
            if await agent.microledgers.is_exists(name):
                await agent.microledgers.reset(name)
            raise RuntimeError(f'Creation of new ledger was terminated with error: \n"{explain}"')


async def commit_transactions(
        my_did: str, ledger_name: str, transactions: List[Transaction], ttl: int, stream_id: str, handler=None
):
    async with get_connection() as agent:
        my_verkey = await agent.wallet.did.key_for_local_did(my_did)
        logger = await StreamLogger.create(stream=stream_id, cb=handler)
        state_machine = simple.state_machines.MicroLedgerSimpleConsensus(
            crypto=agent.wallet.crypto,
            me=Pairwise.Me(my_did, my_verkey),
            pairwise_list=agent.pairwise_list,
            microledgers=agent.microledgers,
            transports=agent,
            logger=logger,
            time_to_live=ttl
        )
        # Add signature to transactions
        signed_transactions = []
        for txn in transactions:
            if 'msg~sig' in txn:
                del txn['msg~sig']
            signature = await sign(agent.wallet.crypto, dict(txn), my_verkey)
            del signature['sig_data']
            txn['msg~sig'] = signature
            signed_transactions.append(Transaction.create(txn))
        # FIRE !!!
        ledger = await agent.microledgers.ledger(ledger_name)
        success, txns_committed = await state_machine.commit(
            ledger=ledger,
            participants=settings.PARTICIPANTS,
            transactions=signed_transactions
        )
        if success:
            await orm.store_transactions(
                ledger=ledger_name,
                transactions=txns_committed
            )
        else:
            if state_machine.problem_report:
                explain = state_machine.problem_report.explain
            else:
                explain = ''
            raise RuntimeError(f'Accepting of new transactions was terminated with error: \n"{explain}"')


class WsTransactions(AsyncJsonWebsocketConsumer):

    TYP_CREATE_LEDGER = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/create-ledger'
    TYP_ISSUE_TXN = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/issue-transaction'
    TYP_PROGRESS = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/progress'

    @sentry_capture_exceptions
    async def connect(self):
        qs = self.scope.get('query_string', None)
        if qs:
            qs = qs.decode()
            qs_items = qs.split('&')
            for item in qs_items:
                if '=' in item:
                    key, value = item.split('=')
                    if key.lower() == 'token':
                        token = await load_token(value)
                        if token:
                            await self.accept()
                            return
            await self.close()
        else:
            await self.close()

    @sentry_capture_exceptions
    async def receive_json(self, payload, **kwargs):
        if '@type' in payload:
            if payload['@type'] == self.TYP_CREATE_LEDGER:
                for attr in ['name', '@id', 'time_to_live', 'genesis']:
                    if attr not in payload:
                        await self.send_problem_report_and_close(REQUEST_ERROR, f'Missing [{attr}] attribute in request')
                    if not payload.get(attr, None):
                        await self.send_problem_report_and_close(REQUEST_ERROR, f'[{attr}] attribute is empty')
                    for txn in payload['genesis']:
                        await self._validate_txn(txn)
                try:
                    ttl = payload.get('time_to_live', 30)
                    genesis = [Transaction.create(**txn) for txn in payload['genesis']]
                    ledger_id = await create_new_ledger(
                        my_did=settings.AGENT['entity'],
                        name=payload['name'],
                        genesis=genesis,
                        ttl=ttl,
                        stream_id='ledgers',
                        handler=self.route_event_to_client
                    )
                    msg = {
                        '@type': self.TYP_PROGRESS,
                        '@id': uuid.uuid4().hex,
                        'ledger': {
                            'name': payload['name'],
                            'id': ledger_id
                        },
                        'done': True
                    }
                    await self.send_json(msg)
                    await self.close()
                except Exception as e:
                    if isinstance(e, SiriusPromiseContextException):
                        explain = e.printable
                    else:
                        explain = str(e)
                    await self.send_problem_report_and_close(
                        REQUEST_PROCESSING_ERROR, explain
                    )
                    return
            elif payload['@type'] == self.TYP_ISSUE_TXN:
                txn = payload
                await self._validate_txn(txn)
                ttl = payload.pop('time_to_live', 30)
                txn = Transaction.create(**payload)
                try:
                    await commit_transactions(
                        my_did=settings.AGENT['entity'],
                        ledger_name=txn['ledger']['name'],
                        transactions=[txn],
                        ttl=ttl,
                        stream_id='transactions',
                        handler=self.route_event_to_client
                    )
                    msg = {
                        '@type': self.TYP_PROGRESS,
                        '@id': uuid.uuid4().hex,
                        'ledger': {
                            'name': txn['ledger']['name'],
                        },
                        'done': True
                    }
                    await self.send_json(msg)
                    await self.close()
                except Exception as e:
                    if isinstance(e, SiriusPromiseContextException):
                        explain = e.printable
                    else:
                        explain = str(e)
                    await self.send_problem_report_and_close(
                        REQUEST_PROCESSING_ERROR, explain
                    )
                    return
            else:
                await self.send_problem_report_and_close(
                    REQUEST_ERROR, 'Unexpected @type = "%s"' % payload['@type']
                )
        else:
            await self.send_problem_report_and_close(
                REQUEST_ERROR, 'Missing @type attribute in request'
            )

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data:
            payload = json.loads(bytes_data.decode('utf-8'))
        else:
            payload = json.loads(text_data)
        await self.receive_json(payload)

    async def send_problem_report_and_close(self, problem_code: str, explain: str):
        report = build_problem_report(problem_code, explain)
        await self.send_json(report)
        await self.close()

    async def route_event_to_client(self, event: dict):
        progress = event.get('payload').get('progress', None)
        message = event.get('payload').get('message', None)
        if message or progress:
            msg = {
                '@type': self.TYP_PROGRESS,
                '@id': uuid.uuid4().hex
            }
            if progress is not None:
                msg['progress'] = progress
            if message is not None:
                msg['message'] = message
            await self.send_json(msg)

    async def _validate_txn(self, txn: dict):
        for attr in ['@type', '@id', 'no', 'date', 'cargo', 'departure_station', 'arrival_station', 'doc_type', 'ledger']:
            if attr not in txn:
                await self.send_problem_report_and_close(REQUEST_ERROR, f'Transaction: missing [{attr}] attribute')
                raise ValueError
            if not txn.get(attr, None):
                await self.send_problem_report_and_close(REQUEST_ERROR, f'Transaction: [{attr}] attribute is empty')
                raise ValueError
            ledger_name = txn.get('ledger', {}).get('name')
            if not ledger_name:
                await self.send_problem_report_and_close(REQUEST_ERROR, 'Transaction: ledger.name is empty')
                raise ValueError
            waybill = txn.get('waybill', {})
            if waybill:
                waybill_no = waybill.get('no', None)
                wagon_no = waybill.get('wagon_no', None)
                if not (waybill_no or wagon_no):
                    await self.send_problem_report_and_close(REQUEST_ERROR, 'Transaction: you should fill [waybill] attributes')
                    raise ValueError
            attachments = txn.get('~attach', [])
            for attach in attachments:
                for fld in ['mime_type', '@id', 'filename', 'data']:
                    val = attach.get(fld, None)
                    if not val:
                        await self.send_problem_report_and_close(REQUEST_ERROR, f'Transaction attachment: missing [{fld}] attribute')
                        raise ValueError
                url = attach.get('data', {}).get('json', {}).get('url', None)
                md5 = attach.get('data', {}).get('json', {}).get('md5', None)
                if not (url and md5):
                    await self.send_problem_report_and_close(REQUEST_ERROR, f'Transaction attachment: [url] and [md5] should be set')
                    raise ValueError

    async def disconnect(self, code):
        pass


class WsQRCodeAuth(AsyncJsonWebsocketConsumer):

    @sentry_capture_exceptions
    async def connect(self):
        if settings.AGENT['entity']:
            _ = [(name, value) for name, value in self.scope['headers'] if name == b'cookie']
            cookies = _[0][1].decode() if len(_) > 0 else ''
            await self.accept()
        else:
            await self.close()

