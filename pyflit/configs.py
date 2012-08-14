# -*- coding: utf-8 -*-

import sys
import utils

default_user_agent = 'Mozilla/5.0 '\
    '(Macintosh; Intel Mac OS X 10_6_8) '\
    'AppleWebKit/534.57.2 (KHTML, like Gecko) '\
    'Version/5.1.7 Safari/534.57.2'

# Replace the http proxy address
proxies = {'http':'http://127.0.0.1:8080'}

settings = {}

settings['default_headers'] = {
    'User-Agent': default_user_agent,
    'Accept-Encoding': 'gzip, deflate',
    'Accept': '*/*'
    }

settings['allow_proxy'] = False
settings['proxies'] = proxies

settings['timeout'] = 30
settings['accept_gzip'] = True

# HTTP Redirection
settings['allow_redirects'] = True
settings['max_redirects'] = 10
_codes = {
    301: ('moved_permanently', 'moved', '\\o-'),
    302: ('found',),
    303: ('see_other', 'other'),
    307: ('temporary_redirect', 'temporary_moved', 'temporary')
    }

dict_rev = utils.dict_list_reverse(_codes)
codes = utils.DictDotLookup(dict_rev)

# logging more info
settings['verbose'] = sys.stdout

# Use socket.setdefaulttimeout() as fallback
settings['timeout_fallback'] = True
