import hashlib

from django.conf import settings
from sirius_sdk import Agent
from sirius_sdk.agent.microledgers import MicroledgerList

from microledgers.impl import NamespacedMicroledgerList


def get_auth_connection_key_seed() -> str:
    auth_key = "%s:auth" % str(settings.AGENT['entity'])
    seed_auth_key = hashlib.md5(auth_key.encode()).hexdigest()
    return seed_auth_key


def get_agent_microledgers(agent: Agent) -> MicroledgerList:
    if settings.SINGLE_MICROLEDGER_PER_ENTITY:
        ml = NamespacedMicroledgerList(namespace=settings.AGENT['entity'], proxy_to=agent.microledgers)
    else:
        ml = agent.microledgers
    return ml
