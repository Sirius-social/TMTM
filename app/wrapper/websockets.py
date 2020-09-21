import json
import uuid
from typing import List, Dict
from contextlib import asynccontextmanager
from django.conf import settings
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from sirius_sdk import Agent, P2PConnection, Pairwise
from sirius_sdk.agent.consensus import simple
from sirius_sdk.agent.microledgers import Transaction

from scripts.management.commands.decorators import sentry_capture_exceptions


REQUEST_ERROR = 'request_error'


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


async def create_new_ledger(my_did: str, name: str, genesis: List[Transaction], ttl: int):
    async with get_connection() as agent:
        agent = alloc_agent_connection()
        my_verkey = await agent.wallet.did.key_for_local_did(my_did)
        state_machine = simple.state_machines.MicroLedgerSimpleConsensus(
            crypto=agent.wallet.crypto,
            me=Pairwise.Me(my_did, my_verkey),
            pairwise_list=agent.pairwise_list,
            microledgers=agent.microledgers,
            transports=agent,
            time_to_live=ttl
        )
        await state_machine.init_microledger(
            ledger_name=name,
            participants=settings.PARTICIPANTS,
            genesis=genesis
        )



class WsTransactions(AsyncJsonWebsocketConsumer):

    TYP_CREATE_LEDGER = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/create-ledger'
    TYP_ISSUE_TXN = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/issue-transaction'

    @sentry_capture_exceptions
    async def connect(self):
        await self.accept()

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
            elif payload['@type'] == self.TYP_ISSUE_TXN:
                txn = payload
                await self._validate_txn(txn)
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
