import os
import json
import uuid
import logging
import asyncio
from typing import Optional, Union
from datetime import datetime
from typing import List, Dict
from contextlib import asynccontextmanager
from django.conf import settings
from django.urls import reverse
from sirius_sdk.messaging import Message
from django.contrib.auth.models import User as UserModel
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from sirius_sdk import Agent, P2PConnection, Pairwise, Endpoint
from sirius_sdk.agent.consensus import simple
from sirius_sdk.agent.microledgers import Transaction
from sirius_sdk.errors.exceptions import SiriusPromiseContextException
from sirius_sdk.agent.aries_rfc.utils import sign
from sirius_sdk.agent.aries_rfc.feature_0095_basic_message import Message as TextMessage
from sirius_sdk.agent.aries_rfc.feature_0113_question_answer import Question, Answer
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol import Invitation, Inviter, ConnRequest
from sirius_sdk.agent.aries_rfc.feature_0036_issue_credential import Issuer, \
    AttribTranslation as IssuerAttribTranslation, ProposedAttrib
from sirius_sdk.agent.aries_rfc.feature_0037_present_proof import Verifier, \
    AttribTranslation as VerifierAttribTranslation

from scripts.management.commands.decorators import sentry_capture_exceptions
from scripts.management.commands.logger import StreamLogger
from scripts.management.commands import orm
from scripts.management.commands.run_smart_contracts import parse_and_store_gu
from ui.models import QRCode, PairwiseRecord, CredentialQR, AuthRef
from wrapper.models import UserEntityBind
from wrapper.utils import get_agent_microledgers
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
            microledgers=get_agent_microledgers(agent),
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
        my_did: str, ledger_name: Union[str, list], transactions: List[Transaction], ttl: int, stream_id: str, handler=None
):
    async with get_connection() as agent:
        my_verkey = await agent.wallet.did.key_for_local_did(my_did)
        logger = await StreamLogger.create(stream=stream_id, cb=handler)
        state_machine = simple.state_machines.MicroLedgerSimpleConsensus(
            crypto=agent.wallet.crypto,
            me=Pairwise.Me(my_did, my_verkey),
            pairwise_list=agent.pairwise_list,
            microledgers=get_agent_microledgers(agent),
            transports=agent,
            logger=logger,
            time_to_live=ttl,
            locks=agent.locks
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
        ledger_txns = {}
        if isinstance(ledger_name, str):
            ledger = await agent.microledgers.ledger(ledger_name)
            success, txns_committed = await state_machine.commit(
                ledger=ledger,
                participants=settings.PARTICIPANTS,
                transactions=signed_transactions
            )
        elif isinstance(ledger_name, list):
            ledgers = []
            for name in ledger_name:
                ledger = await agent.microledgers.ledger(name)
                ledgers.append(ledger)
                ledger_txns[name] = await ledger.get_all_transactions()
            success = await state_machine.commit_in_parallel(
                ledgers=ledgers,
                participants=settings.PARTICIPANTS,
                transactions=signed_transactions
            )
        else:
            raise RuntimeError('Unexpected ledger_name type: ' + str(type(ledger_name)))
        if success:
            if isinstance(ledger_name, str):
                await orm.store_transactions(
                    ledger=ledger_name,
                    transactions=txns_committed
                )
            elif isinstance(ledger_name, list):
                for name in ledger_name:
                    ledger = await agent.microledgers.ledger(name)
                    pred_txn_count = len(ledger_txns[name])
                    all_txns = await ledger.get_all_transactions()
                    txns_committed = all_txns[pred_txn_count:]
                    await orm.store_transactions(
                        ledger=name,
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
    TYP_GU11 = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/gu-11'
    TYP_GU12 = 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/gu-12'

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
                    message = 'В системе зарегистрирован новый контейнер %s' % payload['name']
                    os.system('python /app/manage.py notify_pairwise "%s"' % message)
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
                    message = 'Для контейнера %s зарегистрирована новая операция' % txn['ledger']['name']
                    os.system('python /app/manage.py notify_pairwise "%s"' % message)
                except Exception as e:
                    if isinstance(e, SiriusPromiseContextException):
                        explain = e.printable
                    else:
                        explain = str(e)
                    await self.send_problem_report_and_close(
                        REQUEST_PROCESSING_ERROR, explain
                    )
                    return
            elif payload['@type'] in [self.TYP_GU11, self.TYP_GU12]:
                txn = payload
                try:
                    await self._validate_txn(txn)
                    category = 'gu11' if payload['@type'] == self.TYP_GU11 else 'gu12'
                    await database_sync_to_async(parse_and_store_gu)(txn, category)
                    await self.broadcast_for_all_participants(txn)
                    await self.route_event_to_client(
                        event={
                            'payload': {
                                'progress': 100,
                                'message': 'Transaction successfully accepted and was broadcast for all participants'
                            }
                        }
                    )
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

    @staticmethod
    async def broadcast_for_all_participants(txn: dict):
        async with get_connection() as agent:
            entity = settings.AGENT['entity']
            participants_dids = [did for did in settings.PARTICIPANTS_META.keys() if did != entity]
            for did in participants_dids:
                to = await agent.pairwise_list.load_for_did(did)
                if to:
                    msg = Message(txn)
                    print(f'============ SEND message to DID: {did}  =======')
                    print(json.dumps(msg, indent=2, sort_keys=True))
                    print('================================================')
                    await agent.send_to(msg, to)
                else:
                    print('Empty pairwise for DID: ' + did)

    async def _validate_txn(self, txn: dict):
        if txn.get('@type', None) in [self.TYP_GU11, self.TYP_GU12]:
            for attr in ['@type', '@id', 'no', 'date', 'cargo_name', 'depart_station', 'arrival_station', 'month', 'year', 'tonnage', 'shipper']:
                if attr not in txn:
                    await self.send_problem_report_and_close(REQUEST_ERROR, f'Missing [{attr}] attribute')
                    raise ValueError
            if txn['@type'] == self.TYP_GU11:
                decade = txn.get('decade', None)
                if decade is None:
                    await self.send_problem_report_and_close(REQUEST_ERROR, f'Missing decade attribute for "ГУ-11"')
                    raise ValueError
        else:
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

    def __init__(self, *args, **kwargs):
        self.conn_listener = None
        super().__init__(*args, **kwargs)

    @sentry_capture_exceptions
    async def connect(self):
        if settings.AGENT['entity']:
            _ = [(name, value) for name, value in self.scope['headers'] if name == b'cookie']
            cookies = _[0][1].decode() if len(_) > 0 else ''
            cookies = [s.strip(' ') for s in cookies.split(';') if '=' in s]
            qr_url = None
            for cookie in cookies:
                name, value = cookie.split('=')
                if name == 'qr':
                    qr_url = value.replace("'", '').replace('"', '')
                    break
            if qr_url:
                qr_code_model = await self.load_qr_code_model(qr_url)
                if qr_code_model:
                    endpoint = Endpoint(**qr_code_model.my_endpoint)
                    self.conn_listener = asyncio.ensure_future(
                        self.connection_listener(qr_code_model.connection_key, endpoint)
                    )
                    await self.accept()
                else:
                    await self.close()
            else:
                await self.close()
        else:
            await self.close()

    async def disconnect(self, code):
        if self.conn_listener:
            self.conn_listener.cancel()
        await super().disconnect(code)

    async def connection_listener(self, connection_key: str, my_endpoint: Endpoint):
        print('connection_key: ' + connection_key)
        async with get_connection() as agent:
            assert isinstance(agent, Agent)
            listener = await agent.subscribe()
            async for event in listener:
                if event.recipient_verkey == connection_key and isinstance(event.message, ConnRequest):
                    await self.send_json(
                        {'in_progress': True}
                    )
                    logging.error('============= INVITER: Connection request ==============')
                    logging.error(json.dumps(event, indent=2, sort_keys=True))
                    logging.error('==================================')
                    entity = settings.AGENT['entity']
                    state_machine = Inviter(transports=agent)
                    try:
                        success, pairwise = await state_machine.create_connection(
                            me=Pairwise.Me(
                                did=entity, verkey=settings.PARTICIPANTS_META[entity]['verkey']
                            ),
                            connection_key=connection_key,
                            request=event.message,
                            my_endpoint=my_endpoint
                        )
                    except Exception as e:
                        await self.send_json(
                            {'in_progress': False}
                        )
                        logging.error('============= INVITER: exception ==============')
                        print(repr(e))
                        logging.error('==================================')
                    if success:
                        await agent.pairwise_list.ensure_exists(pairwise)
                        logging.error('========= INVITER: PAIRWISE ============')
                        logging.error(json.dumps(pairwise.metadata, indent=2, sort_keys=True))
                        pairwise_in_db = await self.store_pairwise_in_db(pairwise)
                        logging.error('========= INVITER: PAIRWISE STORED IN DATABASE ============')
                        logging.error('========== START VERIFY=======')
                        try:
                            machine = Verifier(
                                prover=pairwise, pool_name=settings.AGENT['ledger'],
                                api=agent.wallet.anoncreds, cache=agent.wallet.cache,
                                transports=agent
                            )
                            success = await machine.verify(
                                proof_request={
                                    "nonce": await agent.wallet.anoncreds.generate_nonce(),
                                    "name": "Account-Credentials",
                                    "version": "0.1",
                                    "requested_attributes": {
                                        "attr1_referent": {
                                            "name": "username",
                                            "restrictions": {
                                                "issuer_did": entity
                                            }
                                        }
                                    },
                                    "requested_predicates": {}
                                },
                                comment='Validate yourself to Enter service',
                                translation=[
                                    VerifierAttribTranslation('username', 'Username')
                                ],
                                proto_version='1.0'
                            )
                            logging.error(f'******* VERIFY RESULT: {success} ********')
                            if success:
                                logging.error('=========== PROOF =========')
                                logging.error(json.dumps(machine.requested_proof, indent=2, sort_keys=True))
                                username_value = machine.requested_proof['revealed_attrs']['attr1_referent']['raw']
                                await self.set_username_for_pairwise(pairwise_in_db, username_value)
                                user_bind = UserEntityBind.objects.filter(
                                    entity=settings.AGENT['entity'],
                                    user__username=username_value
                                ).first()
                                if user_bind:
                                    ref = AuthRef.objects.create(uid=uuid.uuid4().hex, user=user_bind.user)
                                    route_url = reverse('auth-ref', kwargs={'uid': ref.uid})
                                    logging.error(f'===== ROUTE URL: {route_url} ====')
                                    await self.send_json(
                                        {'url': route_url, 'in_progress': True}
                                    )
                                    await agent.send_to(
                                        message=TextMessage(
                                            content='Welcome to ' + settings.PARTICIPANTS_META[entity]['label'],
                                            locale='en'
                                        ),
                                        to=pairwise
                                    )
                                else:
                                    raise RuntimeError('Not found account')
                            else:
                                raise RuntimeError('Proof invalid')
                        except Exception as e:
                            await self.send_json(
                                {'in_progress': False, 'error': str(e)}
                            )
                            logging.error('========== EXCEPTION WHILE VERIFY =======')
                            logging.error(repr(e))
                            logging.error('======================================')
                            await agent.send_to(
                                message=TextMessage(
                                    content='Authorization error: ' + str(e),
                                    locale='en'
                                ),
                                to=pairwise
                            )

    @staticmethod
    async def load_qr_code_model(url: str) -> QRCode:

        def sync(url_: str) -> QRCode:
            inst = QRCode.objects.filter(url=url_).first()
            return inst

        return await database_sync_to_async(sync)(url)

    @staticmethod
    async def store_pairwise_in_db(pairwise: Pairwise) -> PairwiseRecord:

        def sync(p: Pairwise):
            model = PairwiseRecord.objects.filter(
                their_did=p.their.did, entity=settings.AGENT['entity']
            ).first()
            if model:
                model.metadata = p.metadata
                model.save()
            else:
                model = PairwiseRecord.objects.create(
                    their_did=p.their.did, entity=settings.AGENT['entity'], metadata=p.metadata
                )
            return model

        return await database_sync_to_async(sync)(pairwise)

    @staticmethod
    async def set_username_for_pairwise(pairwise: PairwiseRecord, username: str):

        def sync(p: PairwiseRecord, u: str):
            p.username = u
            p.save()

        await database_sync_to_async(sync)(pairwise, username)


class WsQRCredentialsAuth(AsyncJsonWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        self.conn_listener = None
        super().__init__(*args, **kwargs)

    @sentry_capture_exceptions
    async def connect(self):
        if settings.AGENT['entity']:
            _ = [(name, value) for name, value in self.scope['headers'] if name == b'cookie']
            cookies = _[0][1].decode() if len(_) > 0 else ''
            cookies = [s.strip(' ') for s in cookies.split(';') if '=' in s]
            username = None
            for cookie in cookies:
                name, value = cookie.split('=')
                if name == 'username':
                    username = value.replace("'", '').replace('"', '')
                    break
            if username:
                cred_qr_model = await self.load_cred_qr_model(username)
                if cred_qr_model:
                    endpoint = Endpoint(**cred_qr_model.qr.my_endpoint)
                    self.conn_listener = asyncio.ensure_future(
                        self.connection_listener(username, cred_qr_model.qr.connection_key, endpoint)
                    )
                    await self.accept()
                else:
                    await self.close()
            else:
                await self.close()
        else:
            await self.close()

    async def disconnect(self, code):
        if self.conn_listener:
            self.conn_listener.cancel()
        await super().disconnect(code)

    @staticmethod
    async def connection_listener(username: str, connection_key: str, my_endpoint: Endpoint):
        print('username: ' + username)
        print('connection_key: ' + connection_key)
        entity = settings.AGENT['entity']
        async with get_connection() as agent:
            assert isinstance(agent, Agent)
            listener = await agent.subscribe()
            async for event in listener:
                if event.recipient_verkey == connection_key and isinstance(event.message, ConnRequest):
                    logging.error('============= INVITER: Connection request ==============')
                    logging.error(json.dumps(event, indent=2, sort_keys=True))
                    logging.error('==================================')
                    state_machine = Inviter(transports=agent)
                    try:
                        success, pairwise = await state_machine.create_connection(
                            me=Pairwise.Me(
                                did=entity, verkey=settings.PARTICIPANTS_META[entity]['verkey']
                            ),
                            connection_key=connection_key,
                            request=event.message,
                            my_endpoint=my_endpoint
                        )
                    except Exception as e:
                        logging.error('============= INVITER: exception ==============')
                        print(repr(e))
                        logging.error('==================================')
                    if success:
                        await agent.pairwise_list.ensure_exists(pairwise)
                        logging.error('========= INVITER: PAIRWISE ============')
                        logging.error(json.dumps(pairwise.metadata, indent=2, sort_keys=True))
                        pairwise_in_db = await WsQRCodeAuth.store_pairwise_in_db(pairwise)
                        await WsQRCodeAuth.set_username_for_pairwise(pairwise_in_db, username)
                        logging.error('========= INVITER: PAIRWISE STORED IN DATABASE ============')
                        logging.error('===============================')
                        logging.error('====== START ISSUING ===========')
                        try:
                            ledger = agent.ledger(name=settings.AGENT['ledger'])
                            fetched = await ledger.fetch_schemas(name='Account', version='1.0', submitter_did=entity)
                            schema = fetched[0]
                            fetched = await ledger.fetch_cred_defs(schema_id=schema.id)
                            cred_def = fetched[0]
                            machine = Issuer(holder=pairwise, api=agent.wallet.anoncreds, transports=agent)
                            await machine.issue(
                                values={
                                    'username': username,
                                    'role': 'employee'
                                },
                                schema=schema,
                                cred_def=cred_def,
                                comment='Your credentials. Use it to authorize later.',
                                cred_id='credential-for-' + username,
                                translation=[
                                    IssuerAttribTranslation('username', 'Username')
                                ],
                                preview=[
                                    ProposedAttrib('username', username)
                                ]
                            )
                            logging.error('========= ISSUING SUCCESSFULLY STOPPED ============')
                            await agent.send_to(
                                message=TextMessage(
                                    content='You may authorize with this credentials later',
                                    locale='en'
                                ),
                                to=pairwise
                            )
                        except Exception as e:
                            logging.error('====== EXCEPTION While issuing ===========')
                            logging.error(repr(e))
                            logging.error('==========================================')

    @staticmethod
    async def load_cred_qr_model(username: str) -> CredentialQR:

        def sync(username_: str) -> CredentialQR:
            inst = CredentialQR.objects.filter(username=username_).first()
            return inst

        return await database_sync_to_async(sync)(username)
