import pycurl
import io
import threading
import time
import math
import argparse
import os
import urllib.parse
import urllib.request
import platform
import ssl
args = argparse.ArgumentParser()
args.add_argument("-t", "--threads", type=int, default=5, help="Number of threads (parallel downloads/requests) to use when downloading (default 5)")
args.add_argument("-s", "--chunk-size", type=int, default=10, help="Chunk size in MB (default 10)")
args.add_argument("-o", "--output", type=str, default=None, help="Output filename (or full path) override")
args.add_argument("url", type=str, help="URL to download")
args = args.parse_args()
def format_size(size_in_bytes, decimal_places=2):
    # Define size units, including up to YB (Yottabytes)
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    
    # If the size is 0, return 0 B
    if size_in_bytes == 0:
        return "0 B"
    
    # Calculate the index for the unit using logarithm
    index = min(int(math.log(size_in_bytes, 1024)), len(units) - 1)
    
    # Convert size to the appropriate unit
    size = size_in_bytes / (1024 ** index)
    
    # Format to the specified decimal places and append unit
    return f"{size:.{decimal_places}f} {units[index]}"
last_stdout_length = 0
def overwrite_stdout(string):
    global last_stdout_length
    print('\r' + string + (' ' * (last_stdout_length - len(string))), end='')
    last_stdout_length = len(string)
class HeaderProcessor:
    def __init__(self):
        self.headers = {}
        self._line_count = 0
    def process_header(self, line):
        if self._line_count != 0 and line.decode().strip(): # Skip the first line (the status header) and empty lines
            key, value = line.decode().split(':', 1)
            self.headers[key.lower()] = value.strip()
        self._line_count += 1
def http_get_nobody(url, headers={}):
    r = urllib.request.Request(url, headers=headers, method='GET')
    r = urllib.request.urlopen(r, context=ssl.create_default_context())
    d = {
        'status': r.getcode(),
        'headers': r.headers
    }
    r.close()
    return d
def find_ca_cert_bundle_linux():
    common_paths = [
        "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
        "/etc/pki/tls/certs/ca-bundle.crt",    # Red Hat/CentOS/Fedora
        "/etc/ssl/ca-bundle.pem",              # OpenSUSE
        "/etc/ca-certificates/trust-source/ca-bundle.crt",  # Arch Linux
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path
    
    raise Exception("Could not find a suitable CA bundle for your OS")
def http_get(url, headers={}):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    if platform.system() == 'Linux':
        # a fix for pycurl on Linux
        c.setopt(pycurl.CAINFO, find_ca_cert_bundle_linux())
    c.setopt(pycurl.USERAGENT, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
    rheaders = HeaderProcessor()
    c.setopt(pycurl.HEADERFUNCTION, rheaders.process_header)
    for key, value in headers.items():
        c.setopt(pycurl.HTTPHEADER, [key + ': ' + value])
    d = io.BytesIO()
    c.setopt(pycurl.WRITEDATA, d)
    c.perform()
    return {
        'status': c.getinfo(pycurl.HTTP_CODE),
        'body': d.getvalue(),
        'headers': rheaders.headers
    }
def get_chunk(url, OUTPUT_FILE, offset, length, index):
    global write_index
    global running
    global total_received
    r = http_get(url, headers={'Range': 'bytes=%d-%d' % (offset, offset + length - 1)})
    if r['status'] != 206:
        raise Exception('Unexpected status %d' % r['status'])
    while write_index != index:
        time.sleep(0.01)
    OUTPUT_FILE.write(r['body'])
    total_received += len(r['body'])
    write_index += 1
    running -= 1
r = http_get_nobody(args.url)
if r['status'] != 200:
    raise Exception('Unexpected status %d' % r['status'])
if not 'accept-ranges' in r['headers'] or not 'bytes' in r['headers']['accept-ranges']:
    raise Exception('Server does not support byte ranges (and therefore this script will not work)')
CHUNK_SIZE = 1024 * 1024 * args.chunk_size
START_TIME = time.time()
TOTAL_SIZE = int(r['headers']['content-length'])
OUTPUT_FILENAME = args.output
if not OUTPUT_FILENAME:
    OUTPUT_FILENAME = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(args.url).path))
OUTPUT_FILE = open(OUTPUT_FILENAME, 'wb')
running = 0
offset = 0
write_index = 0
index = 0
total_received = 0
can_exit = False
print('Downloading to "%s" with %s threads...' % (OUTPUT_FILENAME, args.threads))
def status_update():
    global TOTAL_SIZE
    global total_received
    global START_TIME
    global can_exit
    while True:
        overwrite_stdout('\rDownloaded %s/%s bytes in %.2f seconds (%s/s)' % (format_size(total_received), format_size(TOTAL_SIZE), time.time() - START_TIME, format_size(total_received / (time.time() - START_TIME))))
        if total_received == TOTAL_SIZE:
            while running > 0: # wait for all threads to finish
                time.sleep(0.01)
            print('\nDone!')
            can_exit = True
            break
        time.sleep(0.1)
threading.Thread(target=status_update, daemon=True).start()
while offset <= TOTAL_SIZE:
    running += 1
    threading.Thread(target=get_chunk, args=(args.url, OUTPUT_FILE, int(offset), CHUNK_SIZE if offset + CHUNK_SIZE <= TOTAL_SIZE else TOTAL_SIZE - offset, int(index)), daemon=True).start()
    index += 1
    offset += CHUNK_SIZE
    while running >= args.threads:
        time.sleep(0.01)
while not can_exit:
    time.sleep(0.01)