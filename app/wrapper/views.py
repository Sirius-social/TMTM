import uuid

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework_extensions.routers import ExtendedDefaultRouter
from django.conf import settings
from sirius_sdk import Agent, P2PConnection
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping import Ping

from ui.utils import run_async


# Create your views here.
class MaintenanceViewSet(viewsets.GenericViewSet):
    """Maintenance"""
    renderer_classes = [JSONRenderer]

    @action(methods=["GET", "POST"], detail=False)
    def check_health(self, request):
        run_async(
            self.participants_trust_ping(),
            timeout=15
        )
        return Response(dict(success=True, message='OK'))

    @staticmethod
    async def participants_trust_ping():
        if settings.AGENT['entity']:
            # extract neighbours
            neighbours = {did: meta for did, meta in settings.PARTICIPANTS_META.items() if did != settings.AGENT['entity']}
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
                ping_id = uuid.uuid4().hex
                for their_did, meta in neighbours.items():
                    to = await agent.pairwise_list.load_for_did(their_did)
                    await agent.send_to(
                        message=Ping(comment='ping-id: %s' % ping_id),
                        to=to
                    )
            finally:
                await agent.close()


MaintenanceRouter = ExtendedDefaultRouter()
# Maintenance subsystem
MaintenanceRouter.register(r'maintenance', MaintenanceViewSet, 'maintenance')
