TMTM
==================
Sirius SDK wrapper. Maintaining Sirius agent via web-service


Therminology
==================

  - **Agent**:
  - **Distributed state-machines**:


Start Guide: step-by-step
==========================

  - **Step 1**: As noticed `here <https://github.com/Sirius-social/TMTM/tree/master/transactions#motivation>`_, wrapper is intermediate component between independent IT system and Blockchain. Take **username** + **password** from you admin. TMTM wrapper service use **BasicAuth**
  - **Step 2**: Wrapper dump all successful ended transactions in local database. You may get access for some useful services:

    - **<your_domain>/ledgers/**: get list of all ledgers on your side
    - **<your_domain>/ledgers/<ledger-id>/transactions/**: get list of all blockchain transactions that mapped to specific ledger
    - **<your_domain>/maintenance/check_health/**: check your service health - script will ping all participants via P2P connections to check pongs from all of them
    - **<your_domain>/maintenance/allocate_token/**: allocate secret token to get access to transactions request service via websocket

  - **Step 3**: allocate secret-token to give ability to send commands to blockchain

  - **Step 4**: Open websocket commands endpoint via earlier allocated **Token**

    - connect to websocket **wss://<your_domain>/transactions?token=<your-token>**
    - to create new cargo-container blockchain ledger, send `create-ledger command <https://github.com/Sirius-social/TMTM/tree/master/transactions#create-ledger---create-ledger-handle-new-ledgers>`_ via websocket
    - to issue new transactions with documents for existing ledger, send `issue-transaction command <https://github.com/Sirius-social/TMTM/tree/master/transactions#issue-transaction---issue-transaction>`_ via websocket
    - server will notify you about new events via several message formatsЖ

      - to notify user and collect logs server will send `progress messages <https://github.com/Sirius-social/TMTM/tree/master/transactions#progress---transaction-progress>`_
      - to notify user about errors server will send `problem report message <https://github.com/Sirius-social/TMTM/tree/master/transactions#problem_report---errors-reporting>`_

    - every time request transaction is done regardless of OK or Error server will close websocket connection

  - **Step 5**: to make new request, repeat Step-4
