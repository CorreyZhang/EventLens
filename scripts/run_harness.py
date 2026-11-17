"""Keep the local Harness launch token in RAM and register its local entry."""
import re
import sys
import json
import signal
import subprocess
import urllib.request

process=subprocess.Popen(sys.argv[1:],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
def stop(signum,frame):
    if process.poll() is None:process.send_signal(signum)
signal.signal(signal.SIGINT,stop)
signal.signal(signal.SIGTERM,stop)
try:
    for line in process.stdout:
        match=re.search(r'http://127\.0\.0\.1:3080/\?token=[A-Za-z0-9_-]+',line)
        if match:
            try:
                req=urllib.request.Request('http://127.0.0.1:8765/api/harness/runtime',data=json.dumps({'url':match.group()}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=10) as response:response.read()
                print('Harness ready: http://127.0.0.1:8765/workstation',flush=True)
            except Exception:
                print('Harness started; local entry registration failed. Start EventLens first, then restart this launcher.',flush=True)
        else:print(line,end='',flush=True)
finally:
    if process.poll() is None:process.terminate()
sys.exit(process.wait())
