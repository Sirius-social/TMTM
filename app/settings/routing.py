from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf.urls import url

from wrapper.websockets import WsTransactions


application = ProtocolTypeRouter(
    {
        "websocket":
            URLRouter([
                url("^events/(?P<stream_id>.*)$", WsTransactions),
            ])
    }
)
