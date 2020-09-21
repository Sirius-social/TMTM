from urllib.parse import urlsplit

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.http.response import HttpResponseRedirect
from sirius_sdk import Agent, P2PConnection

from wrapper.models import Ledger
from .utils import run_async


class AgentCredentialsSerializer(serializers.Serializer):

    server_address = serializers.CharField(required=True, max_length=1024)
    credentials = serializers.CharField(required=True, max_length=1024)
    my_verkey = serializers.CharField(required=True, max_length=128)
    my_secret_key = serializers.CharField(required=True, max_length=128)
    agent_verkey = serializers.CharField(required=True, max_length=128)
    entity = serializers.CharField(required=True, max_length=128)

    def update(self, instance, validated_data):
        return dict(**instance, **validated_data)

    def create(self, validated_data):
        data = dict(validated_data)
        data['credentials'] = data['credentials'].encode('ascii')
        return data


class TransactionsView(APIView):
    template_name = 'transactions.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        params = {k: v for k, v in request.query_params.items()}
        params_from_settings = dict(
            credentials=settings.AGENT['credentials'],
            server_address=settings.AGENT['server_address'],
            entity=settings.AGENT['entity'],
            my_verkey=settings.AGENT['my_verkey'],
            my_secret_key=settings.AGENT['my_secret_key'],
            agent_verkey=settings.AGENT['agent_verkey']
        )
        for k, v in params_from_settings.items():
            params[k] = params.get(k, None) or v
        ser = AgentCredentialsSerializer(data=params)
        try:
            ser.is_valid(raise_exception=True)
            try:
                credentials = ser.create(ser.validated_data)
                run_async(self.check_agent_credentials(credentials))
            except Exception as e:
                raise serializers.ValidationError('Invalid agent connection credentials or keys')
        except serializers.ValidationError as e:
            print(str(e))
            return Response(status=400, data=str(e).encode())
        else:
            entity = credentials['entity']
            if settings.AGENT['is_sea']:
                doc_types = {
                    'default': 'Сonnaissement',
                    'values': [
                        {'id': 'Сonnaissement', 'caption': 'Коносамент'},
                        {'id': 'Manifest', 'caption': 'Манифест'},
                        {'id': 'CargoPlan', 'caption': 'Грузовой план'},
                        {'id': 'LogisticInfo', 'caption': 'Перевозочная информация'}
                    ]
                }
            else:
                doc_types = {
                    'default': 'WayBill',
                    'values': [
                        {'id': 'WayBill', 'caption': 'СМГС Накладная'},
                        {'id': 'Invoice', 'caption': 'Инвойс'},
                        {'id': 'PackList', 'caption': 'Упаковочный лист'},
                        {'id': 'QualityPassport', 'caption': 'Паспорт качества'},
                        {'id': 'GoodsDeclaration', 'caption': 'Декларация на товары'},
                        {'id': 'WayBillRelease', 'caption': 'Накладная на отпуск запасов на сторону'}
                    ]
                }
            curr_abs_url = request.build_absolute_uri()
            parts = urlsplit(curr_abs_url)
            ws_url = 'wss://' if request.is_secure() else 'ws://' + parts.netloc + '/transactions'
            return Response(data={
                'ledgers': [{'name': ledger.name, 'id': ledger.id} for ledger in Ledger.objects.filter(entity=entity).all()[:200]],
                'logo': '/static/logos/%s' % settings.PARTICIPANTS_META[entity]['logo'],
                'label': settings.PARTICIPANTS_META[entity]['label'],
                'cur_date': str(timezone.datetime.now().strftime('%d.%m.%Y')),
                'upload_url': str(reverse('upload')),
                'doc_types': doc_types,
                'ws_url': ws_url
            })

    @staticmethod
    async def check_agent_credentials(credentials: dict):
        agent = Agent(
            server_address=credentials['server_address'],
            credentials=credentials['credentials'],
            p2p=P2PConnection(
                my_keys=(credentials['my_verkey'], credentials['my_secret_key']),
                their_verkey=credentials['agent_verkey']
            )
        )
        await agent.open()
        try:
            ok = await agent.ping()
            assert ok is True
            print('======== AGENT PING OK ========')
        finally:
            await agent.close()


class IndexView(APIView):
    template_name = 'index.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        if settings.AGENT['entity']:
            return HttpResponseRedirect(redirect_to=reverse('transactions'))
        else:
            return Response(data={})


class TestView(APIView):
    template_name = 'test.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        return Response(data={})
