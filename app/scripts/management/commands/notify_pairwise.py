import asyncio
import logging
from typing import List

import sirius_sdk
from sirius_sdk.agent.wallet import NYMRole
from django.conf import settings
from channels.db import database_sync_to_async
from django.core.management.base import BaseCommand

from ui.models import PairwiseRecord
from wrapper.models import Ledger, Transaction


class Command(BaseCommand):

    help = 'Notify pairwise with message'
    STATISTIC_TEXT = 'Статистика'
    UNSUBSCRIBE_TEXT = 'Отписаться'
    SUBSCRIBE_TEXT = 'Подписаться'

    def add_arguments(self, parser):
        parser.add_argument('message', type=str)

    def handle(self, *args, **options):
        message = options['message']

        async def run(theirs: List[str]):

            async def process_pairwise(their_did: str):
                to = await sirius_sdk.PairwiseList.load_for_did(their_did)
                if to:
                    question = sirius_sdk.aries_rfc.Question(
                        valid_responses=[self.STATISTIC_TEXT, self.UNSUBSCRIBE_TEXT],
                        question_text='Новое событие',
                        question_detail=message
                    )
                    question.set_ttl(60)
                    success, answer = await sirius_sdk.aries_rfc.ask_and_wait_answer(question, to)
                    if success and isinstance(answer, sirius_sdk.aries_rfc.Answer):
                        await self.process_answer(answer, to)

            coros = [process_pairwise(did) for did in theirs]
            await asyncio.wait(coros, timeout=120, return_when=asyncio.ALL_COMPLETED)

        dids = [rec.their_did for rec in PairwiseRecord.objects.filter()]
        asyncio.get_event_loop().run_until_complete(run(dids))

    @classmethod
    async def process_answer(cls, answer: sirius_sdk.aries_rfc.Answer, their: sirius_sdk.Pairwise):

        def set_subscription(their_did: str, flag: bool):
            rec = PairwiseRecord.objects.filter(their_did=their_did).first()
            if rec:
                rec.subscribe = flag
                rec.save()

        def load_statistic():
            return Ledger.objects.count(), Transaction.objects.count()

        if answer.response == cls.UNSUBSCRIBE_TEXT:
            await database_sync_to_async(set_subscription)(their.their.did, False)
            await sirius_sdk.send_to(
                message=sirius_sdk.aries_rfc.Message(
                    content='Вы отписаны от уведомлений.',
                    locale='ru'
                ),
                to=their
            )
        elif answer.response == cls.SUBSCRIBE_TEXT:
            await database_sync_to_async(set_subscription)(their.their.did, True)
            await sirius_sdk.send_to(
                message=sirius_sdk.aries_rfc.Message(
                    content='Вы подписаны на уведомления.',
                    locale='ru'
                ),
                to=their
            )
        elif answer.response == cls.STATISTIC_TEXT:
            ledger_cnt, txn_cnt = await database_sync_to_async(load_statistic)()
            await sirius_sdk.send_to(
                message=sirius_sdk.aries_rfc.Message(
                    content='На текущий момент в системе:\nКонтейнеров: %d\nНакладных: %d' % (ledger_cnt, txn_cnt),
                    locale='ru'
                ),
                to=their
            )
        else:
            await sirius_sdk.send_to(
                message=sirius_sdk.aries_rfc.Message(
                    content='Неизвестный ответ',
                    locale='ru'
                ),
                to=their
            )

