==================================
Simple consensus procedure
==================================

- Authors: `Emin <emin@uniser.az>`_, `Elshad <elshad_947@mail.ru>`_, `Pavel Minenkov <https://github.com/Purik>`_, `Talgat Umarbaev <https://github.com/umarbaev>`_
- Since: 2020/09/07

Summary
===============
TODO: Описать контекст происходящего, как мы решаем проблематику BFT

Motivation
===============
TODO: Motivation (see example: https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple)
Написать про необходимость определить форматы транзакций для каждой из форм докумнтов


Tutorial
===============
TODO: Tutorial (see example: https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple)
Написать про типы транзакций, расписать суть и роль каждого типа

Пример JSON транзакции:

.. code-block:: python

  {
      "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/simple-consensus/1.0/problem_report",
      "@id": "1129fbc9-b9cf-4191-b5c1-ee9c68945f42",
      "problem-code": "request_not_accepted",
      "explain": "Transaction has not metadata",
      "~thread": {
        "thid": "simple-consensus-txn-98fd8d72-80f6-4419-abc2-c65ea39d0f38"
      }
  }
