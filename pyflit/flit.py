# -*- coding: utf-8 -*-

import os
import sys
import shutil
import time

import socket
from threading import Thread

from .graunching import (
    RequestException,
    Timeout,
    URLRequired,
    TooManyRedirects
)
from . import utils
from .configs import settings, codes

PY2 = sys.version_info[0] == 2
if PY2:
    range = xrange
    from urllib2 import Request, ProxyHandler, build_opener, HTTPError, URLError
    from urlparse import urlparse, urljoin, urlsplit
    from urllib import quote, unquote
    from Queue import Queue
else:
    from urllib.request import Request, ProxyHandler, build_opener
    from urllib.parse import urlparse, urljoin, urlsplit, quote, unquote
    from urllib.error import HTTPError, URLError
    from queue import Queue


REDIRECT_STATE = (codes.moved, codes.found, codes.other, codes.temporary_moved)


def get_opener(handlers=[], headers={}, proxies={}):
    """Get HTTP URL opener and call its `open()` method to open an URL.

    Arguments:
    - `handlers`: list, handlers support cookie, authority,
                  and other advanced HTTP features.
    - `headers`: dictionary, be treated as if add_header() was called
                 with each key and value as arguments, often used to
                 "spoof" the `User-Agent` header or `Referer` header, etc.
    - `proxies`: dictionary, URL of the proxy,
                 e.g. {'http': 'http://<host>:<port>'},
                 if your proxy requires authentication:
                 {'http': 'http://<user>:<password>@<host>:<port>'}
    """
    _handlers = []
    _handlers.extend(handlers)

    # proxy handler
    http_proxy = proxies or \
        settings.get('allow_proxy') and settings.get('proxies', None)
    if http_proxy:
        try:
            _handlers.append(ProxyHandler(http_proxy))
        except Exception as e:
            print("\n==> Waring: proxy invalid, please check.")
            print(e)

    # gzip/deflate/bzip2 compression handler
    if settings.get('accept_gzip'):
        encoding_handler = utils.ContentEncodingProcessor()
        _handlers.append(encoding_handler)

    # redirect handler
    _handlers.append(utils.HTTPRedirectHandler)

    opener = build_opener(*_handlers)

    # Add HTTP Request Headers
    # default HTTP Headers in configures
    _headers = settings.get('default_headers')

    # dictionary of HTTP Headers to attach
    _headers.update(headers)

    # remove if we have a value in default headers
    if _headers:
        normal_keys = [k.capitalize() for k in _headers]
        for key, val in opener.addheaders[:]:
            # default key, value: 'User-agent', 'Python-urllib/2.7'
            # see python doc
            if key not in normal_keys:  # list search
                continue
            opener.addheaders.remove((key, val))
        # Extend `addheaders` of the opener, dict to tuple list
        opener.addheaders.extend(_headers.items())

    return opener


class PyFlitRequest(object):
    """A simple class to process HTTP url requests, e.g. get the http response,
    process the url content, and more.
    """
    def __init__(self, opener, config=settings):
        """
        Arguments:
        - `opener`: OpenerDirector object,
                    call its open() method to open url request.
        - `config`: dictionary, a bunch of settings, see the config module.
        """

        self._opener = opener

        # Configurations for the request
        self.config = dict(config or [])

    def build_resp(self, resp, is_error):
        """Build URL response to generate a dictionary with
        its original url address, status code, headers, content,
        charset, and the response itself if error occurred.

        Arguments:
        - `resp`: HTTPResponse, Response object.
        - `is_error`: Boolean, flag to tell whether error occurred.
        """
        def build(resp, is_error=False):
            response = dict()

            response['url'] = resp.geturl()
            response['status_code'] = 1 and resp.getcode() or None
            response['headers'] = resp.info()
            response['content'] = resp.read()
            if PY2:
                response['charset'] = response['headers'].getparam('charset')
            else:
                response['charset'] = response['headers'].get_param('charset')
            response['fo'] = resp
            if is_error:
                response['error'] = resp
            return response

        history = []

        r = build(resp, is_error)

        rurl = r.get('url')
        status_code = r.get('status_code')
        headers = r.get('headers')
        if status_code in REDIRECT_STATE:
            url_re = headers.get('location', None)
            while(((self.config.get('allow_redirects')) or
                   (status_code is codes.see_other)) and
                  (not (rurl == url_re)) and
                  ('location' in headers)):
                r.get('fo').close()

                if not len(history) < self.config.get('max_redirects'):
                    raise TooManyRedirects()

                history.append(r)

                # Handle redirection without scheme
                if url_re.startswith('//'):
                    parsed_url = urlparse(rurl)
                    url_re = '%s:%s' % (parsed_url.scheme, rurl)
                    print(url_re)
                # Facilitate non-RFC2616-compliant 'location' headers
                # (e.g. '/path/to/resource' instead of
                #  'http://domain.top-level-domain/path/to/resource')
                if not urlparse(url_re).netloc:
                    url_re = urljoin(rurl,
                                     quote(unquote(url_re)))
                    print(url_re)
                r = self.get_url_chunk(url_re)
                rurl = r.get('url')
                status_code = r.get('status_code')
                headers = r.get('headers')

            r['history'] = history

        return r

    def get_url_response(self, url_req):
        """Send HTTP URL request, return the response
        with a flag to check if error occurs.

        Arguments:
        - `url_req`: string, HTTP request URL or Request object.
        """
        is_error = False

        if not url_req:
            raise URLRequired

        try:
            try:
                resp = self._opener.open(url_req,
                                         timeout=self.config.get('timeout'))
            except TypeError as err:
                if 'timeout' not in str(err):
                    raise
                if self.config.get('timeout_fallback'):
                    old_timeout = socket.getdefaulttimeout()
                    socket.setdefaulttimeout(self.config.get('timeout'))

                resp = self._opener.open(url_req)

                if self.config.get('timeout_fallback'):
                    socket.setdefaulttimeout(old_timeout)
        except (HTTPError, URLError) as why:
            if hasattr(why, 'reason'):
                if isinstance(why.reason, socket.timeout):
                    why = Timeout(why)

            print("\n==> %s\n    when visit '%s'" % (why, url_req))
            is_error = True
            return (why, is_error)
        else:
            return (resp, is_error)

    def get_url_chunk(self, url_req):
        """Open HTTP URL and return the data chunk dictionary,
        see method `PyFlitRequest.build_resp()` to find the keys in it.

        Arguments:
        - `url_req`: string, HTTP request URL or Request object.
        """
        resp, is_error = self.get_url_response(url_req)
        chunk = self.build_resp(resp, is_error)
        return chunk

    def get_url_headers(self, url_req):
        """Send HTTP URL and return its HTTP response headers.

        Arguments:
        - `url_req`: string, HTTP request URL or Request object.
        """
        resp, is_error = self.get_url_response(url_req)
        if is_error:
            return None

        return resp.info()

    def get_url_size(self, url_req):
        """Get url content length from http response headers
        or 0 if error occurs or not exists.

        Arguments:
        - `url_req`: string, HTTP request URL or Request object.
        """
        length = 0
        headers = self.get_url_headers(url_req)

        if headers:
            if PY2:
                content_length = headers.getheaders('Content-Length')
                if content_length:
                    content_length = content_length[0]
            else:
                content_length = headers.get('Content-Length', 0)
            length = content_length and int(content_length) or 0

        if not length:
            raise RequestException("Couldn't get file size from url\n[URL]: %s" %
                                   url_req)
        return length

    def get_url_file_name(self, url_req):
        """Get output file name from the URL response headers or the URL.
        Note that the method itself is not reliable.

        Arguments:
        - `url_req`: string, HTTP request URL or Request object.
        """
        filename = ''

        headers = self.get_url_headers(url_req)
        if headers and 'Content-Disposition' in headers:
            cd = dict(map(lambda x: x.strip().split('=')
                          if '=' in x else (x.strip(), ''),
                          headers['Content-Disposition'].split(';')))
            if 'filename' in cd:
                filename = cd['filename'].strip("\"'")
                if filename:
                    return filename

        # try to get file name from the request url
        if not filename:
            resp, is_error = self.get_url_response(url_req)
            if not is_error:
                filename = os.path.basename(urlsplit(resp.geturl())[2])

        if not filename:
            raise RequestException("Couldn't get file name from url\n[URL]: %s" %
                                   url_req)
        return filename


class MultiTaskingThread(Thread):
    """Multiple tasks downloading thread for fetching URLs.
    """

    def __init__(self, opener, queue_task, queue_chunk):
        """
        Arguments:
        - `opener`: function object,
                    open the URL request and return data chunk,
                    e.g. PyFlitRequest.get_url_chunk() method.
        - `queue_task`: Queue, tasks queue.
        - `queue_chunk`: Queue, data chunk queue.
        """
        Thread.__init__(self)
        self._opener = opener
        self.daemon = True
        self._queue_task = queue_task
        self._queue_chunk = queue_chunk

    def run(self):
        """HTTP url downloading thread.
        """
        while 1:
            # get a url from the queue
            url_req = self._queue_task.get()

            if not url_req:
                if self._queue_task.empty():
                    self._queue_chunk.put(None)
                break

            chunk = {}
            try:
                chunk = self._opener(url_req)
                if chunk:
                    self._queue_chunk.put(chunk)
            except Exception as e:
                print("\n==> Error fetching: %s" % url_req)
                print(e)
            finally:
                # signals to queue that job is done
                self._queue_task.task_done()
            time.sleep(0.1)
        self._queue_task.task_done()


class MultiTasking(object):
    """Multi-threaded of multi-tasks downloading, then process the data chunk.
    """
    def __init__(self, threads_number, opener):
        """
        Arguments:
        - `threads_number`: int, number of threads to download.
        - `opener`: function object,
                    open the URL request and return data chunk,
                    e.g. PyFlitRequest.get_url_chunk() method.
        """
        self._threads_number = threads_number
        self._opener = opener
        self.queue_task = Queue()
        self.queue_chunk = Queue()

    def _push_tasks(self, tasks=[]):
        """
        Arguments:
        - `tasks`: list, HTTP URLs to fetch.
        """
        for task in tasks:
            self.queue_task.put(task)
        # Tasks have been added
        for _ in range(self._threads_number):
            self.queue_task.put(None)

    def __call__(self, tasks=[]):
        """
        Arguments:
        - `tasks`: list, HTTP URLs to fetch.
        """
        self._push_tasks(tasks)

        for i in range(self._threads_number):
            task_thread = MultiTaskingThread(self._opener,
                                             self.queue_task,
                                             self.queue_chunk)
            task_thread.start()

        while 1:
            chunk = self.queue_chunk.get()
            if chunk:
                self.queue_chunk.task_done()
                yield chunk
            else:
                break
            time.sleep(0.1)
        self.queue_chunk.task_done()

    def __del__(self):
        time.sleep(0.3)
        self.queue_task.join()
        self.queue_chunk.join()


class SegmentingThread(Thread):
    """Multi-segment file downloading thread.
    """
    def __init__(self, opener, url_req, filename, ranges=0):
        """
        Arguments:
        - `opener`: OpenerDirector object,
                    call its open() method to open url request.
        - `url_req`: string, http request URL.
        - `filename`: string, output file name.
        - `ranges`: list, start to end mark of the url fetch range.
        """
        Thread.__init__(self)
        self.daemon = True
        self._opener = opener
        self._url_req = url_req
        self._filename = filename
        self._ranges = ranges
        self.fetched = 0

    def run(self):
        """Working thread process of multi-segmenting downloading.
        """
        try:
            self.fetched = os.path.getsize(self._filename)
        except OSError:
            self.fetched = 0

        # rebuild start mark, pause and resume download
        self.startmark = self._ranges[0] + self.fetched
        # if completed
        if self.startmark >= self._ranges[1]:
            # print("Part %s has been fetched over." % self._filename)
            return

        self.size_per_time = 16384  # 16KByte/time

        # Add range to headers
        req = Request(self._url_req)
        req.add_header("Range",
                       "bytes=%d-%d" % (self.startmark, self._ranges[1]))
        # IO
        self.chunkhandle = self._opener.open(req)
        chunk = self.chunkhandle.read(self.size_per_time)
        while chunk:
            fileobj = open(self._filename, "ab+")
            try:
                fileobj.write(chunk)
            finally:
                fileobj.close()

            self.fetched += len(chunk)
            chunk = self.chunkhandle.read(self.size_per_time)


class MultiSegmenting(object):
    """Multi-segment file downloading for fetching big size file.
    """
    def __init__(self, opener):
        """
        Arguments:
        - `opener`: OpenerDirector object,
                    call its open() method to open url request.
        """
        self._opener = opener
        self.flitter = PyFlitRequest(self._opener)

    def split_segment(self, url_size, segment_number):
        """Split file size into list tuple of segments with the giving number.

        Arguments:
        - `url_size`: int,
                      total url file size, call `self.get_url_size()` method.
        - `segment_number`: int,
                            the numbers you want to separate the file size.
        """
        segment_size = url_size / segment_number
        ranges = [(i * segment_size,
                   (i + 1) * segment_size - 1)
                  for i in range(segment_number - 1)]
        ranges.append((segment_size * (segment_number - 1), url_size - 1))
        return ranges

    def _islive(self, tasks):
        for task in tasks:
            if task.isAlive():
                return True
        return False

    def __call__(self, url_req, segments=2):
        url_size = self.flitter.get_url_size(url_req)

        ranges = self.split_segment(url_size, segments)
        output = self.flitter.get_url_file_name(url_req)
        filename = ["%s_tmp_%d.pfb" % (output, i) for i in range(segments)]

        tasks = []
        for i in range(segments):
            task = SegmentingThread(self._opener,
                                    url_req,
                                    filename[i],
                                    ranges[i])
            task.start()
            tasks.append(task)

        time.sleep(0.5)
        while self._islive(tasks):
            fetched = sum([t.fetched for t in tasks])
            utils.progressbar(url_size, fetched)

        fileobj = open(output, 'wb+')
        try:
            for i in filename:
                with open(i, 'rb') as f:
                    shutil.copyfileobj(f, fileobj)
                os.remove(i)
        finally:
            fileobj.close()

        finished_size = os.path.getsize(output)
        if abs(url_size - finished_size) <= 10:
            utils.progressbar(url_size, finished_size, 100)


def flit_tasks(tasks, threads_number, opener=get_opener()):
    """Multiple tasks downloading and process the data chunk, mostly used
    when grabbing amount of web pages.

    Arguments:
    - `tasks`: list, HTTP URLs to fetch.
    - `thread_number`: int, number of threads to download.
    - `opener`: OpenerDirector object,
                call its open() method to open url request.
    """
    request = PyFlitRequest(opener)
    flitter = MultiTasking(threads_number, request.get_url_chunk)
    chunks = flitter(tasks)
    return chunks


def flit_segments(url_req, segment_number=2, opener=get_opener()):
    """Multiple segment file downloading, a replacement of wget. ;-)

    Arguments:
    - `url_req`: string, http request URL.
    - `segment_number`: int, the numbers you want to separate the files.
    - `opener`: OpenerDirector object,
                call its open() method to open url request.
    """
    # Some proxy server couldn't support fetch range feature
    # reset segment_number to 1.
    flitter = MultiSegmenting(opener)
    flitter(url_req, segment_number)
