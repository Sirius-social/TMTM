from typing import List, Union

from sirius_sdk.agent.microledgers import AbstractMicroledgerList, LedgerMeta, Transaction, AbstractMicroledger


class NamespacedMicroledgerList(AbstractMicroledgerList):

    def __init__(self, namespace: str, proxy_to: AbstractMicroledgerList):
        self.__namespace = namespace
        self.__proxy_to = proxy_to

    @property
    def namespace(self) -> str:
        return self.__namespace

    def mangled_name(self, name: str) -> str:
        return f'{self.namespace}/{name}'

    async def create(self, name: str, genesis: Union[List[Transaction], List[dict]]) -> (AbstractMicroledger, List[Transaction]):
        ledger, txns = await self.__proxy_to.create(
            name=self.mangled_name(name),
            genesis=genesis
        )
        return ledger, txns

    async def ledger(self, name: str) -> AbstractMicroledger:
        ledger = await self.__proxy_to.ledger(name=self.mangled_name(name))
        return ledger

    async def reset(self, name: str):
        await self.__proxy_to.reset(name=self.mangled_name(name))

    async def is_exists(self, name: str):
        success = await self.__proxy_to.is_exists(name=self.mangled_name(name))
        return success

    async def leaf_hash(self, txn: Union[Transaction, bytes]) -> bytes:
        value = await self.__proxy_to.leaf_hash(txn)
        return value

    async def list(self) -> List[LedgerMeta]:
        value = await self.__proxy_to.list()
        return value
