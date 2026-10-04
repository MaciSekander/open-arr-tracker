"""Serve the built site locally: python3 pipeline/serve.py [port]"""
import functools, http.server, sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / 'site'
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
print(f'http://localhost:{port}')
http.server.ThreadingHTTPServer(('127.0.0.1', port), handler).serve_forever()
