import os
import json
import uuid
import argparse
from urllib.parse import urljoin

import requests
import websocket
from requests.auth import HTTPBasicAuth


BASE = os.path.realpath(os.path.dirname(__file__))
FILE_NAME = 'sample.pdf'


def run():
    parser = argparse.ArgumentParser(description='Issue GU transaction sample')
    parser.add_argument('base_url', type=str, help='Your service URL')
    parser.add_argument('login', type=str, help='Username')
    parser.add_argument('password', type=str, help='Password')
    args = parser.parse_args()

    base_url = args.base_url
    login = args.login
    password = args.password
    print('base_url: %s' % base_url)
    print('login: %s' % login)
    print('password: %s' % password)

    # Step-1: Allocate Token
    url = urljoin(base_url, '/maintenance/allocate_token/')
    resp = requests.get(url, auth=HTTPBasicAuth(login, password))
    assert resp.status_code == 200
    auth_token = resp.json()['token']

    # Step-2: Upload sample doc
    file_path = os.path.join(BASE, FILE_NAME)
    assert os.path.isfile(file_path)
    url_upload = urljoin(base_url, '/upload')
    resp = requests.post(url_upload, auth=HTTPBasicAuth(login, password), files={'file': open(file_path, 'rb')})
    assert resp.status_code == 200, 'Error while uploading file'
    url_file = resp.json()['url']
    md5_file = resp.json()['md5']

    # Step-2: Issue GU-11 transaction
    txn = {
        '@type': 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/gu-11',
        '@id': uuid.uuid4().hex,
        "no": "100000-03",
        "date": "01/01/2020",
        "cargo_name": "Сборный контейнер",
        "depart_station": "Karagandi",
        "arrival_station": "Poti",
        "month": "Май",
        "year": "2020",
        "decade": "2",
        "tonnage": "10",
        "shipper": "ООО ТревелСейл",
        "~attach": [
            {
                "@id": "document-1",
                "mime_type": "application/pdf",
                "filename": FILE_NAME,
                "data": {
                    "json": {
                        "url": url_file,
                        "md5": md5_file
                    }
                }
            }
        ]
    }

    # Step-3: Connect to Websocket service endpoint
    ws_url = urljoin(base_url, 'transactions?token=%s' % auth_token).replace('https://', 'wss://')
    ws = websocket.create_connection(ws_url)
    assert ws.connected is True

    # Step-4: FIRE!!!
    payload = json.dumps(txn).encode('utf-8')
    ws.send(payload)
    s = ws.recv()
    response = json.loads(s)
    if response['@type'] == 'https://github.com/Sirius-social/TMTM/tree/master/transactions/1.0/progress' and response['progress'] == 100:
        print('Success')
    else:
        print('Something wrong!!!')


if __name__ == '__main__':
    run()
