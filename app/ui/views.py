from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import serializers
from django.conf import settings
from sirius_sdk import Agent, P2PConnection

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
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        ser = AgentCredentials(data=request.query_params)
        try:
            ser.is_valid(raise_exception=True)
            try:
                credentials = ser.create(ser.validated_data)
                run_async(self.check_agent_credentials(credentials))
            except:
                raise serializers.ValidationError('Invalid agent connection credentials or keys')
        except serializers.ValidationError as e:
            print(str(e))
            raise
        else:
            ledgers = [
                '20-001-0000002',
                '20-001-0000001',
                '20-001-1000000',
                '20-001-1010012',
                '20-001-1102212',
                '20-001-1234453',
                '20-001-0922333',
                '43-201-1000000',
                '43-201-1010012',
                '30-331-0003302',
                '30-011-0000002',
                '30-021-0000001',
                '30-031-1000000',
                '30-041-1010012',
                '30-051-0000002',
            ]
            entity = credentials['entity']
            return Response(data={
                'ledgers': ledgers,
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
