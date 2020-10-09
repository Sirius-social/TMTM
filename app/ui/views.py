import copy
import logging
from urllib.parse import urlsplit

import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.http.response import HttpResponseRedirect
from sirius_sdk import Agent, P2PConnection
from sirius_sdk.agent.aries_rfc.feature_0160_connection_protocol import Invitation

from wrapper.models import Ledger, Token
from wrapper.websockets import get_connection
from ui.models import QRCode
from .utils import run_async


MENU = [
    {'caption': 'Transactions', 'class': 'fa fa-columns m-r-10', 'enabled': True, 'link': reverse_lazy('transactions')},
    {'caption': 'ГУ-11', 'class': 'fa fa-table m-r-10', 'enabled': True, 'link': reverse_lazy('gu11')},
    {'caption': 'ГУ-12', 'class': 'fa fa-table m-r-10', 'enabled': True, 'link': reverse_lazy('gu12')},
    {'caption': 'Грузоперевозки', 'class': 'fa fa-globe m-r-10', 'enabled': False, 'link': None},
    {'caption': 'Морские документы', 'class': 'fa fa-globe m-r-10', 'enabled': False, 'link': None},
    {'caption': 'Admin', 'class': 'fa fa-globe m-r-10', 'enabled': False, 'link': reverse_lazy('admin')},
]


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
    authentication_classes = [SessionAuthentication]
    permission_classes = []

    def get(self, request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return HttpResponseRedirect(redirect_to=reverse('auth'))
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
            is_secure = request.is_secure()
            logging.error('-----------------')
            logging.error('parts.scheme: ' + parts.scheme)
            logging.error('is_secure: ' + str(is_secure))
            logging.error('curr_abs_url: ' + curr_abs_url)
            logging.error('parts.netloc: ' + str(parts.netloc))
            logging.error('-----------------')
            ws_url = 'wss://' if is_secure else 'ws://'
            ws_url += parts.netloc + '/transactions'
            token = Token.allocate(request.user).value
            ws_url += '?token=%s' % token
            menu = copy.copy(MENU)
            menu[-1]['enabled'] = request.user.is_superuser
            return Response(data={
                'menu': menu,
                'active_menu_index': 0,
                'ledgers': [{'name': ledger.name, 'id': ledger.id} for ledger in Ledger.objects.filter(entity=entity).all()[:200]],
                'logo': '/static/logos/%s' % settings.PARTICIPANTS_META[entity]['logo'],
                'label': settings.PARTICIPANTS_META[entity]['label'],
                'cur_date': str(timezone.datetime.now().strftime('%d.%m.%Y')),
                'upload_url': str(reverse('upload')),
                'doc_types': doc_types,
                'ws_url': ws_url,
                'smart_contract_init_ledger_url': str(reverse('smart-contract-init-ledger')),
                'smart_contract_commit_txns_url': str(reverse('smart-contract-commit-txns')),
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


class AdminView(APIView):
    template_name = 'admin.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = [SessionAuthentication]
    permission_classes = []

    def get(self, request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return HttpResponseRedirect(redirect_to=reverse('auth'))
        if not request.user.is_superuser:
            return Response(status=403)
        menu = copy.copy(MENU)
        menu[-1]['enabled'] = request.user.is_superuser
        return Response(data={
            'menu': menu,
            'active_menu_index': 5,
        })


class BaseGUView(APIView):
    template_name = 'gu.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = [SessionAuthentication]
    permission_classes = []

    def get(self, request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return HttpResponseRedirect(redirect_to=reverse('auth'))
        menu = copy.copy(MENU)
        menu[-1]['enabled'] = request.user.is_superuser
        return Response(data={
            'menu': menu,
            'active_menu_index': self.get_active_menu_index(),
            'title': MENU[self.get_active_menu_index()]['caption']
        })

    def get_active_menu_index(self):
        raise NotImplemented


class GU11View(BaseGUView):

    def get_active_menu_index(self):
        return 1


class GU12View(BaseGUView):

    def get_active_menu_index(self):
        return 2


class IndexView(APIView):
    template_name = 'index.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        if settings.AGENT['entity']:
            if request.user and request.user.is_authenticated:
                return HttpResponseRedirect(redirect_to=reverse('transactions'))
            else:
                return HttpResponseRedirect(redirect_to=reverse('auth'))
        else:
            return Response(data={})


class LoginSerializer(serializers.Serializer):

    login = serializers.CharField(max_length=36, required=True)
    password = serializers.CharField(max_length=128, required=True)

    def create(self, validated_data):
        return dict(validated_data)

    def update(self, instance, validated_data):
        instance.update(validated_data)
        return instance


class AuthView(APIView):
    template_name = 'auth.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = [SessionAuthentication]
    permission_classes = []

    def get(self, request, *args, **kwargs):
        if not settings.AGENT['entity']:
            return HttpResponseRedirect(redirect_to=reverse('index'))
        if request.user.is_authenticated:
            return HttpResponseRedirect(redirect_to=reverse('transactions'))
        qr = request.COOKIES.get('qr', None)
        if qr:
            resp = requests.get(qr)
            if resp.status_code != 200:
                QRCode.objects.filter(url=qr).all().delete()
                qr = None
            else:
                qr_model = QRCode.objects.filter(url=qr).first()
                if qr_model is None:
                    qr = None
                elif not qr_model.my_endpoint:
                    QRCode.objects.filter(url=qr).all().delete()
                    qr = None
        if not qr:
            qr = run_async(
                self.generate_invitation_qr()
            )
        data = self.get_response_data(request)
        data['qr'] = qr
        resp = Response(data=data)
        resp.set_cookie('qr', qr)
        return resp

    def post(self, request, *args, **kwargs):
        ser = LoginSerializer(data=request.data)
        errors = {}
        try:
            ser.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            for k, v in e.get_full_details().items():
                errors[k] = str(v[0]['message'])
        params = ser.create(ser.validated_data)
        if not errors:
            user = User.objects.filter(
                username=params['login'],
                entities__entity=settings.AGENT['entity']
            ).first()
            if not user:
                errors['login'] = 'Unknown user'
            else:
                ok = user.check_password(params['password'])
                if ok:
                    login(request, user)
                else:
                    errors['password'] = 'Invalid password'
        data = self.get_response_data(request)
        qr = request.COOKIES.get('qr', None)
        if qr:
            data['qr'] = qr
        if errors:
            data['errors'] = errors
            return Response(data=data)
        else:
            return HttpResponseRedirect(redirect_to=reverse('index'))

    @staticmethod
    def get_response_data(request):
        curr_abs_url = request.build_absolute_uri()
        parts = urlsplit(curr_abs_url)
        is_secure = request.is_secure()
        ws_url = 'wss://' if is_secure else 'ws://'
        ws_url += parts.netloc + '/auth'
        entity = settings.AGENT['entity']
        return {
            'logo': '/static/logos/%s' % settings.PARTICIPANTS_META[entity]['logo'],
            'label': settings.PARTICIPANTS_META[entity]['label'],
            'errors': {},
            'ws_url': ws_url
        }

    @staticmethod
    async def generate_invitation_qr():
        entity = settings.AGENT['entity']
        if not entity:
            return None
        async with get_connection() as agent:
            endpoint_address = [e for e in agent.endpoints if e.routing_keys == []][0].address
            connection_key = await agent.wallet.crypto.create_key()
            invitation = Invitation(
                label=settings.PARTICIPANTS_META[entity]['label'],
                endpoint=endpoint_address,
                recipient_keys=[connection_key]
            )
            invitation['did'] = entity
            url = await agent.generate_qr_code(invitation.invitation_url)
            my_endpoint = {
                'address': endpoint_address,
                'routing_keys': []
            }
            QRCode.objects.get_or_create(connection_key=connection_key, url=url, my_endpoint=my_endpoint)
            return url


class LogoutView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        if request.user and request.user.is_authenticated:
            logout(request)
            return HttpResponseRedirect(redirect_to=reverse('auth'))
        else:
            return HttpResponseRedirect(redirect_to=reverse('auth'))


class TestView(APIView):
    template_name = 'test.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        return Response(data={})


class SmartContractInitLedgerView(APIView):
    template_name = 'smart_contract_create_ledger.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        return Response(data={})


class SmartContractCommitView(APIView):
    template_name = 'smart_contract_commit_txns.html'
    renderer_classes = [TemplateHTMLRenderer]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        return Response(data={})