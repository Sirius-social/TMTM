import os

import requests
from requests.auth import HTTPBasicAuth

BASE = os.path.realpath(os.path.dirname(__file__))

url = 'http://localhost:8000/upload'
path = os.path.join(BASE, 'invoice.docx')

assert os.path.isfile(path), 'file does not exists'

resp = requests.post(url, files={'file': open(path, 'rb')}, auth=HTTPBasicAuth('test', 'test'))
assert resp.status_code == 200

data = resp.json()

print('------- response ------')
print(repr(data))
print('-----------------------')


print('> download file')
resp = requests.get(data['url'])
assert resp.status_code == 200

print('--------- file content ---------')
print(repr(resp.content))
