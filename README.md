# Turbo Downloader
A simple python script to download a file fast using threads and http range reqeusts.

# Install
Just install `pycurl`:
```sh
$ pip install pycurl
```

# Usage
```sh
$ python3 turbo-downloader.py --help                        
usage: turbo-downloader.py [-h] [-t THREADS] [-s CHUNK_SIZE] [-o OUTPUT] url

positional arguments:
  url                   URL to download

options:
  -h, --help            show this help message and exit
  -t THREADS, --threads THREADS
                        Number of threads (parallel downloads/requests) to use when downloading (default 5)
  -s CHUNK_SIZE, --chunk-size CHUNK_SIZE
                        Chunk size in MB (default 10)
  -o OUTPUT, --output OUTPUT
                        Output filename (or full path) override
```