import os
from datetime import datetime
from typing import Optional

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework_extensions.routers import ExtendedDefaultRouter
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_extensions.mixins import PaginateByMaxMixin, NestedViewSetMixin
from rest_framework import serializers
from django_downloadview.shortcuts import sendfile
from django.conf import settings
from django.db import transaction
from sirius_sdk import Agent, P2PConnection
from sirius_sdk.agent.aries_rfc.feature_0048_trust_ping import Ping

from ui.utils import run_async
from .models import Ledger, Transaction, Content, Token, GURecord
from .decorators import cross_domain
from .mixins import ExtendViewSetMixin


# Create your views here.
class MaintenanceViewSet(viewsets.GenericViewSet):
    """Maintenance"""
    renderer_classes = [JSONRenderer]

    def get_permissions(self):
        if self.action == 'check_health':
            return []
        else:
            return [IsAuthenticated()]

    @action(methods=["GET", "POST"], detail=False)
    def check_health(self, request):
        ping_id = str(datetime.utcnow())
        run_async(
            self.participants_trust_ping(ping_id),
            timeout=15
        )
        return Response(dict(success=True, ping_id=ping_id, message='OK'))

    @action(methods=["GET", "POST"], detail=False)
    def allocate_token(self, request):
        token = Token.allocate(request.user)
        return Response({'token': token.value})

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


def get_txn_date(txn: Transaction) -> int:
    d = txn.txn.get('date')
    if d:
        try:
            parts = d.split('.')
            if len(parts) == 3:
                for item in parts:
                    if not item.isdigit():
                        d = None
                        break
                if d:
                    day, month, year = parts
                    day = int(day)
                    month = int(month)
                    if len(year) == 2:
                        year = 2000 + int(year)
                    else:
                        year = int(year)
                    d = datetime(day=day, month=month, year=year)
            else:
                d = None
        except:
            d = None
    return d


class LedgerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ledger
        fields = ('id', 'name', 'metadata', 'days_in_way')
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):

    attachments = serializers.SerializerMethodField('get_attachments')
    signer_icon = serializers.SerializerMethodField('get_signer_icon')
    signer_label = serializers.SerializerMethodField('get_signer_label')
    date = serializers.SerializerMethodField('get_date')
    status = serializers.SerializerMethodField('get_status')

    def get_attachments(self, obj):
        collection = obj.txn['~attach']
        return collection

    def get_signer_icon(self, obj):
        signer_verkey = obj.txn.get('msg~sig', {}).get('signer', None)
        if signer_verkey:
            for did, item in settings.PARTICIPANTS_META.items():
                verkey = item['verkey']
                if verkey == signer_verkey:
                    icon_url = '/static/logos/%s' % item['icon']
                    return icon_url
            return None
        else:
            return None

    def get_status(self, obj):
        signer_verkey = obj.txn.get('msg~sig', {}).get('signer', None)
        if signer_verkey:
            if signer_verkey == settings.PARTICIPANTS_META['U9A6U7LZQe4dCh84t3fpTK']['verkey']:
                return 'started'
            elif signer_verkey == settings.PARTICIPANTS_META['6jzbnVE5S6j15afcpC9yhF']['verkey']:
                return 'finished'
            else:
                return 'in_way'
        else:
            return None

    def get_signer_label(self, obj):
        signer_verkey = obj.txn.get('msg~sig', {}).get('signer', None)
        if signer_verkey:
            for did, item in settings.PARTICIPANTS_META.items():
                verkey = item['verkey']
                if verkey == signer_verkey:
                    return item['label']
            return None
        else:
            return None

    def get_date(self, obj):
        return obj.txn.get('date')

    class Meta:
        model = Transaction
        fields = ('txn', 'seq_no', 'metadata', 'attachments', 'signer_icon', 'signer_label', 'date', 'status')
        read_only_fields = fields


class LedgerViewSet(
            viewsets.mixins.RetrieveModelMixin,
            viewsets.mixins.ListModelMixin,
            viewsets.GenericViewSet
        ):

    renderer_classes = [JSONRenderer]
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
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(ledger=self.get_ledger()).order_by('-id')

    def get_ledger(self) -> Optional[Ledger]:
        return self.get_parents_query_dict().get('ledger', None)

    @action(methods=['GET', 'POST'], detail=False)
    def list_with_meta(self, request, *args, **kwargs):
        ledger = Ledger.objects.get(id=self.get_ledger())
        queryset = ledger.transaction_set.order_by('-seq_no').all()
        serializer = self.get_serializer(queryset, many=True)
        txn_first = ledger.transaction_set.first()
        txn_last = ledger.transaction_set.last()
        try:
            if txn_first and txn_last:
                date_start = get_txn_date(txn_first)
                date_stop = get_txn_date(txn_last)
                if date_start and date_stop:
                    delta = date_stop - date_start
                    days_in_way = delta.days
                else:
                    days_in_way = None
            else:
                days_in_way = None
        except:
            days_in_way = None
        data = {
            'results': serializer.data,
            'days_in_way': days_in_way
        }
        return Response(data)


class BaseGUSerializer(serializers.ModelSerializer):
    attachments = serializers.SerializerMethodField('get_attachments')

    def get_attachments(self, obj: GURecord):
        collection = obj.attachments
        return collection

    class Meta:
        model = GURecord
        fields = (
            'no', 'date', 'cargo_name', 'depart_station', 'arrival_station',
            'month', 'year', 'tonnage', 'shipper', 'attachments'
        )
        read_only_fields = fields


class GU11Serializer(BaseGUSerializer):

    class Meta(BaseGUSerializer.Meta):
        fields = list(BaseGUSerializer.Meta.fields) + ['decade']
        read_only_fields = fields


class GU12Serializer(BaseGUSerializer):

    class Meta(BaseGUSerializer.Meta):
        pass


class GU11ViewSet(
            PaginateByMaxMixin, NestedViewSetMixin,
            viewsets.mixins.RetrieveModelMixin,
            viewsets.mixins.ListModelMixin,
            viewsets.GenericViewSet
        ):
    lookup_field = 'id'
    renderer_classes = [JSONRenderer]
    permission_classes = [IsAuthenticated]
    serializer_class = GU11Serializer

    def get_queryset(self):
        return GURecord.objects.filter(
            entity=settings.AGENT['entity'],
            category='gu11'
        ).order_by('-id')


class GU12ViewSet(
            PaginateByMaxMixin, NestedViewSetMixin,
            viewsets.mixins.RetrieveModelMixin,
            viewsets.mixins.ListModelMixin,
            viewsets.GenericViewSet
        ):
    lookup_field = 'id'
    renderer_classes = [JSONRenderer]
    permission_classes = [IsAuthenticated]
    serializer_class = GU12Serializer

    def get_queryset(self):
        return GURecord.objects.filter(
            entity=settings.AGENT['entity'],
            category='gu12'
        ).order_by('-id')


class UploadView(ExtendViewSetMixin, APIView):

    renderer_classes = [JSONRenderer]
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, BasicAuthentication]

    def dispatch(self, request, *args, **kwargs):
        try:
            resp = super().dispatch(request, *args, **kwargs)
        except Exception as e:
            raise
        return resp

    @cross_domain
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file', None)
        if file is None:
            return Response(b'Expected file value', status=400)
        data = {'url': None, 'md5': None, 'filename': None}
        with transaction.atomic():
            content = Content()
            content.set_file(file)
            content.save()
            data['url'] = self.make_full_url(content.url)
            data['md5'] = content.md5
            data['filename'] = content.name
        return Response(data, status=200)


class ContentView(ExtendViewSetMixin, APIView):

    permission_classes = []

    @cross_domain
    def get(self, request, uid, *args, **kwargs):
        content = Content.objects.filter(uid=uid, entity=settings.AGENT['entity']).first()
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

# GU-11 & GU-12
GU11Router = ExtendedDefaultRouter()
GU11Router.register(r'gu-11', GU11ViewSet, 'gu-11')
GU12Router = ExtendedDefaultRouter()
GU12Router.register(r'gu-12', GU12ViewSet, 'gu-12')
