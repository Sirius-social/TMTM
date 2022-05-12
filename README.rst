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
    - **<your_domain>/gu-11/**: fetch all received ГУ-11 transactons
    - **<your_domain>/gu-12/**: fetch all received ГУ-12 transactons
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


Upload service
==========================
You may upload documents and give back md5 and public-url to download one: **<your_domain>/upload**, service will respond json object with **md5**, **url**, **filename**


TMTM High level architecture
==========================

.. image:: https://github.com/Sirius-social/TMTM/blob/master/docs/_static/TMTM.png?raw=true
   :alt: Entry



Installation
============================
Step-1: Configure your organization Wallet (for example use `cloud solution <https://agents.socialsirius.com/>`_)

Step-2: Configure your web application in self-maintained infrastructure

    See `docker-compose.yml` example

        version: '2'
        services:

          cache:
            image: memcached

          redis:
            image: redis:latest

          db:
            image: postgres:9.13
            environment:
              - POSTGRES_PASSWORD=postgres
            volumes:
              - ./db_apps:/var/lib/postgresql/data
              - ./tmp:/tmp

          app:
            image: "socialsirius/tmtm:latest"
            restart: on-failure
            environment:
              - DATABASE_USER=postgres
              - DATABASE_PASSWORD=postgres
              - DATABASE_NAME=postgres
              - DATABASE_HOST=db_apps
              - DJANGO_SETTINGS_MODULE=settings.production
              - REDIS=redis
              - ADMIN_USERNAME=<login>
              - ADMIN_PASSWORD=<password>
              - AGENT_CREDENTIALS=<get from wallet settings.credentials>
              - AGENT_SERVER_ADDRESS=<get from wallet settings.server_uri>
              - AGENT_ENTITY=<you will get this value from by call create-entity command>
              - AGENT_MY_VERKEY=<get from wallet settings.p2p.my_keys[0]>
              - AGENT_MY_SECRET_KEY=<get from wallet settings.p2p.my_keys[1]>
              - AGENT_VERKEY=<get from wallet settings.p2p.their_Verkey>
            volumes:
              - ./uploads:/tmp
              - .settings.py:/app/settings/base.py:ro
            ports:
              - "80:8000"
            depends_on:
              - db_apps


Step-3: create entity (run shell command python manage.py create_entity) and replace env var AGENT_ENTITY

Step-4: register Nym for every participant (python manage.py init_nyms)

Step-5: init p2p network (python manage.py setup_pairwises)

Step-6: create admin user (python manage.py setup_admin)
