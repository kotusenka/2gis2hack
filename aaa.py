import os, asyncio, websockets

for k in ['http_proxy','https_proxy','all_proxy','ftp_proxy',
          'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','FTP_PROXY']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost,::1'

async def hello():
    uri = 'ws://127.0.0.1:8000/ws/aaa'
    async with websockets.connect(uri, open_timeout=100) as websocket:
        print('initial:', await websocket.recv())

asyncio.run(hello())