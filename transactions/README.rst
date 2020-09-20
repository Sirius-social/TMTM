==================================
Wrapper Transactions
==================================

- Authors: `Emin <emin@uniser.az>`_, `Elshad <elshad_947@mail.ru>`_, `Pavel Minenkov <https://github.com/Purik>`_, `Talgat Umarbaev <https://github.com/umarbaev>`_
- Since: 2020/09/07

Summary
===============
As described at `Simple consensus <https://github.com/Sirius-social/sirius-sdk-python/tree/master/sirius_sdk/agent/consensus/simple>`_ docs,
participants may to approve self formats of transactions that will be encapsulated to BFT messages.
This document covers types of transactions that are used in TMTM pilot.

Motivation
===============
We should describe message formats for use-cases that developers will meet in TMTM project:

  - use-case 1: create ledger and handle new ledger construction
  - use-case 2: issue transaction and handle new transactions issuing
  - use-case 3: txn formats should cover all types of documents: SMGS(СМГС), Invoice, etc.
  - use-case 4: sign transaction by self keys to identify committer that is core element of any supply-chain approaches.
  - use-case 5: cover necessity to attach documents (.pdf, .doc, etc.)

Notice that all this messages are not part of consensus procedures. All this messages formats are implemented
to wrap SDK calls by intermediate web service at intermediate period. In production all this formats will be removed
and replaced to native SDK calls in native IT environment and program language.

Tutorial
===============
Transactions examples and attribute descriptions are presented below.


***************************************************
[create-ledger] - create ledger, handle new ledgers
***************************************************
Example of service message for ledger creations. It is make sense every **Cargo Container** is serving in personal Ledger.

.. code-block:: python

  {
      "@type": "https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/create-ledger",
      "@id": "1129fbc9-b9cf-4191-b5c1-ee9c68945f42",
      "name": "Ledger-name-0001112222",
      "genesis" : [
            ...
      ],
      "time_to_live": 15
  }


Every time actor needs to initialize new transaction log, it should initialize transactions ledger by genesis block,
then notify all dealers in **Microledger** context and make sure all of them initialized self copy of transactions log.

- **@id**: (required) - unique id of the message
- **name**: (required) - unique name of the ledger
- **genesis**: (required) - array of transactions that initialize new ledger - genesis block. Notice that **txnMetadata** is reserved attribute that contains ledger-specific data
- **time_to_live**: (optional) - time to live of the state machines

***************************************************
[issue-transaction] - issue transaction
***************************************************
Example of the service message to issue transaction.
It is make sense every **Cargo Container** is serving in personal Ledger. After Cargo container ledger was initialized by
genesis block, any participant (ADY, DKT, GR, etc) may issue self-signed transaction.

.. code-block:: python

  {
      "@type": "https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/issue-transaction",
      "@id": "1129fbc9-b9cf-4191-b5c1-ee9c68945f42",
      "no": "20-001-0000002",
      "date": "14.09.20",
      "cargo": "Kids toys",
      "departure_station": "Караганда",
      "arrival_station": "Актау",
      "doc_type": "WayBill",
      "ledger": {
         "name": "some-ledger"
      },
      "waybill": {
         "no": "xxx-yyy",
         "wagon_no": "WSG-XXX-YYY"
      },
      "~attach": [
         {
            "@id": "document-1",
            "mime_type": "application/pdf",
            "filename": "WayBill_xxx_yyy_zzz.pdf",
            "data": {
              "json": {
                "url": "...",
                "md5": "..."
              }
            }
         },
         {
            "@id": "document-2",
            "mime_type": "image/png",
            "filename": "WayBill_xxx_yyy_zzz_attaches.png",
            "data": {
              "json": {
                "url": "...",
                "md5": "..."
              }
            }
         }
      ],
      "time_to_live": 15,
      "msg~sig": {
          "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/signature/1.0/ed25519Sha512_single",
          "signature": "_Oh48kK9I_QNiBRJfU-_HPAUxyIcrn3Ba8QwspSqiy8AMLMN4h8vbozImSr2dnVS2RaOfimWDgWVtZCTvbdjBQ==",
          "signer": "FEvX3nsJ8VjW4qQv4Dh9E3NDEx1bUPDtc9vkaaoKVyz1"
      }
  }


- **@id**: (required) - unique id of the message
- **no**: (required) - transaction NO
- **date**: (required) - issuing date
- **cargo**: (required) - name of the cargo
- **departure_station**: (required) - Departure station
- **arrival_station**: (required) - Arrival station
- **doc_type**: (required) - Document type, available values:

   - WayBill
   - Invoice
   - PackList
   - QualityPassport
   - GoodsDeclaration
   - WayBillRelease
   - Сonnaissement
   - Manifest
   - CargoPlan
   - LogisticInfo

- **ledger**: (required) - operation ledger

  - **ledger.name**: (required) - name of the ledger
  
- **waybill**: (optional) - if filled when doc_type == "WayBill" | "Сonnaissement" | "Manifest" | "CargoPlan" | "LogisticInfo"
- **time_to_live**: (optional) - time to live of the state machines
- **~attach**: (optional) - list of attached documents. Document should be uploaded and published via URL. See detail at `Aries RFC <https://github.com/hyperledger/aries-rfcs/tree/master/concepts/0017-attachments>`_
- **msg~sig**: (required) - signature of the message according to `Aries RFC 0234 <https://github.com/hyperledger/aries-rfcs/tree/master/features/0234-signature-decorator>`_
