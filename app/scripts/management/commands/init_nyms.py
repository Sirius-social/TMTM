import asyncio
import logging

import sirius_sdk
from sirius_sdk.agent.wallet import NYMRole
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = 'Write NYMs to Ledger'

    def add_arguments(self, parser):
        parser.add_argument('steward_seed', type=str)
        parser.add_argument('ledger_name', type=str)

    def handle(self, *args, **options):
        steward_seed = options['steward_seed']
        ledger_name = options['ledger_name']

        async def run(seed: str, ledger: str):
            steward = sirius_sdk.Agent(
                server_address=settings.AGENT['server_address'],
                credentials=settings.AGENT['credentials'].encode('ascii'),
                p2p=sirius_sdk.P2PConnection(
                    my_keys=(
                        settings.AGENT['my_verkey'],
                        settings.AGENT['my_secret_key']
                    ),
                    their_verkey=settings.AGENT['agent_verkey']
                )
            )
            await steward.open()
            try:
                did_steward, verkey_steward = await steward.wallet.did.create_and_store_my_did(seed=seed)
                for did, meta in settings.PARTICIPANTS_META.items():
                    verkey = meta['verkey']
                    label = meta['label']
                    ok, resp = await steward.wallet.ledger.write_nym(
                        ledger, did_steward, did, verkey, label, NYMRole.TRUST_ANCHOR
                    )
                    if not ok:
                        logging.error('Error while NYM register for "%s"' % did)
                        logging.error(str(resp.get('reason', '')))
            finally:
                await steward.close()

        asyncio.get_event_loop().run_until_complete(run(steward_seed, ledger_name))
