from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf.urls import url

from wrapper.websockets import WsTransactions, WsQRCodeAuth


application = ProtocolTypeRouter(
    {
        "websocket":
            URLRouter([
                # url("^events/(?P<stream_id>.*)$", WsTransactions),
                url("^transactions$", WsTransactions),
                url("^auth$", WsQRCodeAuth),
            ])
    }
)
