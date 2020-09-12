from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import serializers
from django.conf import settings
from sirius_sdk import Agent, P2PConnection

from wrapper.models import Ledger
from .utils import run_async


class AgentCredentials(serializers.Serializer):

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
        ser = AgentCredentials(data=request.query_params)
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
            return Response(data={
                'ledgers': [ledger.name for ledger in Ledger.objects.filter(entity=entity).all()[:200]],
                'logo': '/static/logos/%s' % settings.PARTICIPANTS_META[entity]['logo'],
                'label': settings.PARTICIPANTS_META[entity]['label']
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
        return Response(data={})


class TestView(APIView):
    template_name = 'test.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        return Response(data={})
