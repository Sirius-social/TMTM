from urllib.parse import urlsplit, urlunsplit

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from sirius_sdk import Agent, P2PConnection, Pairwise
from sirius_sdk.agent.connections import Endpoint
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol import Inviter, Invitee, Invitation, ConnRequest

from ui.utils import run_async, run_coroutines


class Command(BaseCommand):

    help = 'Setup Pairwise list'

    def add_arguments(self, parser):
        parser.add_argument('meta_url', type=str)

    def handle(self, *args, **options):
        meta_url = options['meta_url']
        print('======================')
        print('Meta URL: ' + meta_url)
        print('======================')
        resp = requests.get(meta_url)
        assert resp.status_code == 200
        meta = resp.json()

        components = list(urlsplit(meta_url))
        components[2] = ''
        url = urlunsplit(components)

        for outer_name in meta.keys():
            for inner_name in meta.keys():
                if inner_name == outer_name:
                    continue
                print('### establish pairwise %s:%s' % (outer_name, inner_name))
                agent1 = Agent(
                    server_address=url,
                    credentials=meta[outer_name]['credentials'].encode('ascii'),
                    p2p=P2PConnection(
                        my_keys=(
                            meta[outer_name]['p2p']['smart_contract']['verkey'],
                            meta[outer_name]['p2p']['smart_contract']['secret_key'],
                        ),
                        their_verkey=meta[outer_name]['p2p']['agent']['verkey']
                    )
                )
                key1 = list(meta[outer_name]['entities'].keys())[0]
                entity1 = meta[outer_name]['entities'][key1]
                agent2 = Agent(
                    server_address=url,
                    credentials=meta[inner_name]['credentials'].encode('ascii'),
                    p2p=P2PConnection(
                        my_keys=(
                            meta[inner_name]['p2p']['smart_contract']['verkey'],
                            meta[inner_name]['p2p']['smart_contract']['secret_key'],
                        ),
                        their_verkey=meta[inner_name]['p2p']['agent']['verkey']
                    )
                )
                key2 = list(meta[inner_name]['entities'].keys())[0]
                entity2 = meta[inner_name]['entities'][key2]
                run_async(
                    self.establish_connection(agent1, entity1, agent2, entity2),
                    timeout=190
                )
                print('### establish success !')

    @staticmethod
    async def establish_connection(agent1: Agent, entity1: dict, agent2: Agent, entity2: dict):
        await agent1.open()
        await agent2.open()
        try:
            did1 = entity1['did']
            did2 = entity2['did']
            label1 = settings.PARTICIPANTS_META[did1]['label']
            label2 = settings.PARTICIPANTS_META[did2]['label']
            verkey1 = entity1['verkey']
            verkey2 = entity2['verkey']
            exists1 = await agent1.pairwise_list.is_exists(did2)
            exists2 = await agent2.pairwise_list.is_exists(did1)
            if exists1 and exists2:
                print('! connection already exists')
                return
            endpoint1 = [e for e in agent1.endpoints if e.routing_keys == []][0]
            endpoint2 = [e for e in agent2.endpoints if e.routing_keys == []][0]

            connection_key_ = verkey1
            invitation_ = Invitation(
                label=label1,
                recipient_keys=[connection_key_],
                endpoint=endpoint1.address
            )

            async def run_inviter(agent: Agent, connection_key: str, me: Pairwise.Me, my_endpoint: Endpoint):
                listener = await agent.subscribe()
                async for event in listener:
                    if event['recipient_verkey'] == connection_key:
                        request = event['message']
                        assert isinstance(request, ConnRequest)
                        # Setup state machine
                        machine = Inviter(agent)
                        # create connection
                        ok, pairwise = await machine.create_connection(me, connection_key, request, my_endpoint)
                        assert ok is True
                        await agent.pairwise_list.ensure_exists(pairwise)
                        return

            async def run_invitee(agent: Agent, invitation: Invitation, my_label: str, me: Pairwise.Me, my_endpoint: Endpoint):
                # Create and start machine
                machine = Invitee(agent)
                ok, pairwise = await machine.create_connection(
                    me=me, invitation=invitation, my_label=my_label, my_endpoint=my_endpoint
                )
                assert ok
                await agent.pairwise_list.ensure_exists(pairwise)

            # agent1 is inviter, agent2 is invitee
            await run_coroutines(
                run_inviter(
                    agent=agent1,
                    connection_key=connection_key_,
                    me=Pairwise.Me(
                        did=did1,
                        verkey=verkey1
                    ),
                    my_endpoint=endpoint1
                ),
                run_invitee(
                    agent=agent2,
                    invitation=invitation_,
                    my_label=label2,
                    me=Pairwise.Me(
                        did=did2,
                        verkey=verkey2
                    ),
                    my_endpoint=endpoint2
                ),
                timeout=30
            )

        finally:
            await agent1.close()
            await agent2.close()
