from django.conf import settings


class ExtendViewSetMixin(object):

    def get_http_referer(self):
        if settings.DEBUG:
            url_scheme = 'http'
        else:
            url_scheme = 'https'
        if 'HTTP_HOST' in self.request.META:
            return url_scheme + '://' + self.request.META['HTTP_HOST']
        else:
            return url_scheme + '://' + self.request.META['REMOTE_ADDR'] + ':' + \
                   self.request.META['SERVER_PORT']

    def make_full_url(self, url):
        http_referer = self.get_http_referer()
        if not http_referer.endswith('/'):
            http_referer = http_referer + '/'
        if url.startswith('/'):
            url = url[1:]
        return http_referer + url
