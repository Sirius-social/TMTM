from django.http import HttpResponse
from django.core.exceptions import AppRegistryNotReady
from rest_framework.exceptions import APIException

ACC_HEADERS = {'Access-Control-Allow-Origin': '*',
               'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
               'Access-Control-Max-Age': 1000,
               'Access-Control-Allow-Headers': '*'}


def cross_domain(func):
    """ Sets Access Control request headers."""
    def wrap(self, request, *args, **kwargs):
        # Firefox sends 'OPTIONS' request for cross-domain javascript call.
        if request.method != "OPTIONS":
            response = func(self, request, *args, **kwargs)
        else:
            response = HttpResponse()
        for k, v in ACC_HEADERS.items():
            response[k] = v
        return response
    return wrap
