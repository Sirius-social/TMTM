import os
from datetime import datetime
from typing import Optional

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework_extensions.routers import ExtendedDefaultRouter
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_extensions.mixins import PaginateByMaxMixin, NestedViewSetMixin
from rest_framework import serializers
from django_downloadview.shortcuts import sendfile
from django.conf import settings
from django.db import transaction
from sirius_sdk import Agent, P2PConnection
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping import Ping

from ui.utils import run_async
from .models import Ledger, Transaction, Content
from .decorators import cross_domain
from .mixins import ExtendViewSetMixin


# Create your views here.
class MaintenanceViewSet(viewsets.GenericViewSet):
    """Maintenance"""
    renderer_classes = [JSONRenderer]

    @action(methods=["GET", "POST"], detail=False)
    def check_health(self, request):
        ping_id = str(datetime.utcnow())
        run_async(
            self.participants_trust_ping(ping_id),
            timeout=15
        )
        return Response(dict(success=True, ping_id=ping_id, message='OK'))

    @staticmethod
    async def participants_trust_ping(ping_id: str):
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
            print('agent.open()')
            await agent.open()
            print('start ping to all')
            try:
                for their_did, meta in neighbours.items():
                    to = await agent.pairwise_list.load_for_did(their_did)
                    print('ping to: ' + their_did)
                    await agent.send_to(
                        message=Ping(comment=ping_id),
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
    queryset = Ledger.objects.filter(entity=settings.AGENT['entity']).order_by('-id').all()


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


class UploadView(ExtendViewSetMixin, APIView):

    renderer_classes = [JSONRenderer]
    permission_classes = [IsAuthenticated]

    @cross_domain
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file', None)
        if file is None:
            return Response(b'Expected file value', status=400)
        data = {'url': None, 'md5': None}
        with transaction.atomic():
            content = Content()
            content.set_file(file)
            content.save()
            data['url'] = self.make_full_url(content.url)
        return Response(data, status=200)


class ContentView(ExtendViewSetMixin, APIView):

    permission_classes = []

    @cross_domain
    def get(self, request, uid, *args, **kwargs):
        content = Content.objects.filter(uid=uid).first()
        if content:
            return sendfile(request, filename=os.path.join(settings.MEDIA_ROOT, content.uid))
        else:
            return Response(f'Not Found', status=404)


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
