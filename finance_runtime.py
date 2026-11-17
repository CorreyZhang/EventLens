"""Optional local socket transport. No keys are written or returned by this API."""
import json
import os
import socket
PATH='/private/tmp/eventlens-finance.sock'
def available():return os.path.exists(PATH)
def call(payload):
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(100)
    try:
        sock.connect(PATH);sock.sendall((json.dumps(payload,ensure_ascii=False)+'\n').encode())
        with sock.makefile('rb') as stream:result=json.loads(stream.readline(12000000))
    finally:sock.close()
    if not result.get('ok'):raise RuntimeError(result.get('error','Finance runtime unavailable'))
    return result['result']
