# README

Pyflit is a simple Python HTTP downloader. The features it supports are shown below.


## Features

+ HTTP GET
+ multi-threaded fetch multiple URLs
+ multi-segment file fetch
+ gzip/deflate/bzip2 compression supporting
+ a simple progress-bar
+ download pause and resume
+ proxy supporting

## Don't use this package in production!

This package is not well tested and buggy that should not be used in production!


## Simple Tutorial

### HTTP GET

First, get self defined URL opener object, you can specify some handlers to support cookie, authentication and other advanced HTTP features. If you want change the `User-Agent` or add `Referer` in the HTTP request headers, you can also given a self defined `headers` as argument. And more, you can turn on proxy by given a dictionary of proxy address. See the API reference for details.

Example:
```python
handlers = [cookie_handler, redirect_handler]
headers = {'User-Agent': 'Mozilla/5.0 '
           '(Macintosh; Intel Mac OS X 10_9_4) '
           'AppleWebKit/537.77.4 (KHTML, like Gecko) '
           'Version/7.0.5 Safari/537.77.4'}
proxies = {'http': 'http://someproxy.com:8080'}

opener = flit.get_opener(handlers, headers, proxies)
u = opener.open("http://www.python.org")
resp = u.read()
```

### Multiple URLs fetching

You can just call `flit.flit_tasks()` to fetch multiple URLs with specified working thread number, a generator will be returned and you can iterate it to process the data chunks.

Example:
```python
from pyflit import flit

def chunk_process(chunk):
    """Output chunk information.
    """
    print "Status_code: %s\n%s\n%s \nRead-Size: %s\nHistory: %s\n" % (
        chunk['status_code'],
        chunk['url'],
        chunk['headers'],
        len(chunk['content']),
        chunk.get('history', None))

links = ['http://www.domain.com/post/%d/' % i for i in xrange(100, 200)]
thread_number = 5
opener = flit.get_opener([handlers [, headers [, proxies]]])
chunks = flit.flit_tasks(links, thread_number, opener)
for chunk in chunks:
    chunk_process(chunk)
```

### Multiple segment file downloading

Multiple segment file downloading use multiple thread to download the separated part of the URL file, you can simply give two arguments: URL address and the segment number.

Example:
```python
from pyflit import flit

url = "http://www.gnu.org/software/emacs/manual/pdf/emacs.pdf"
segment_number = 2
opener = flit.get_opener([handlers [, headers [, proxies]]])
flit.flit_segments(url, segment_number, opener)
```


## Contributing

You can send pull requests via GitHub or help fix the bugs in the issues list.
