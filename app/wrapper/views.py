import uuid
from typing import Optional

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework_extensions.routers import ExtendedDefaultRouter
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_extensions.mixins import PaginateByMaxMixin, NestedViewSetMixin
from rest_framework import serializers
from django.conf import settings
from sirius_sdk import Agent, P2PConnection
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping import Ping

from ui.utils import run_async
from .models import Ledger, Transaction


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


class LedgerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ledger
        fields = ('id', 'name', 'metadata')
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Transaction
        fields = ('txn', 'seq_no', 'metadata')
        read_only_fields = fields


class LedgerViewSet(
            viewsets.mixins.RetrieveModelMixin,
            viewsets.mixins.ListModelMixin,
            viewsets.GenericViewSet
        ):

    renderer_classes = [JSONRenderer]
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = LedgerSerializer
    queryset = Ledger.objects.filter(entity=settings.AGENT['entity']).all()


class TransactionViewSet(
            PaginateByMaxMixin, NestedViewSetMixin,
            viewsets.mixins.RetrieveModelMixin,
            viewsets.mixins.ListModelMixin,
            viewsets.GenericViewSet
        ):

    lookup_field = 'seq_no'
    renderer_classes = [JSONRenderer]
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(ledger=self.get_ledger()).order_by('-id')

    def get_ledger(self) -> Optional[Ledger]:
        return self.get_parents_query_dict().get('ledger', None)


# Maintenance subsystem
# URL pattern: /maintenance
MaintenanceRouter = ExtendedDefaultRouter()
MaintenanceRouter.register(r'maintenance', MaintenanceViewSet, 'maintenance')

# Ledgers subsystem
# URL pattern: /ledgers
LedgersRouter = ExtendedDefaultRouter()
ledgers_router = LedgersRouter.register(r'ledgers', LedgerViewSet, 'ledgers')
# URL pattern: /ledgers/transactions
ledgers_router.register(r'transactions', TransactionViewSet, 'ledger-txns', parents_query_lookups=['ledger'])
