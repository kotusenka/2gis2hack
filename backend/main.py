from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .db import Base, engine
from .redis_client import get_count, subscribe_count
from .routers.devices import router as devices_router
from .routers.buses import router as buses_router


@asynccontextmanager
async def lifespan(app: FastAPI):
	# create tables
	Base.metadata.create_all(bind=engine)
	yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(devices_router)
app.include_router(buses_router)


@app.get("/health")
async def health():
	return {"status": "ok"}


@app.get("/wb/test", response_class=HTMLResponse)
async def wb_test_page():
	return """
	<!doctype html>
	<html>
	<head>
		<meta charset=\"utf-8\" />
		<title>WS Test</title>
		<style>
			body { font-family: sans-serif; margin: 24px; }
			#log { white-space: pre-wrap; border: 1px solid #ccc; padding: 12px; height: 240px; overflow: auto; }
			input, button { margin: 4px; }
			.row { margin: 8px 0; }
		</style>
	</head>
	<body>
		<h1>WebSocket test</h1>
		<div class=\"row\">
			<label>Bus ID: <input id=\"bus\" value=\"42\" /></label>
			<button id=\"connect\">Connect</button>
			<button id=\"disconnect\" disabled>Disconnect</button>
		</div>
		<div id=\"status\">Disconnected</div>
		<h3>Log</h3>
		<div id=\"log\"></div>
		<script>
		let ws = null;
		const log = (m) => {
			const el = document.getElementById('log');
			el.textContent += m + "\n";
			el.scrollTop = el.scrollHeight;
		};
		const setStatus = (s) => { document.getElementById('status').textContent = s; };

		document.getElementById('connect').onclick = () => {
			const id = document.getElementById('bus').value.trim();
			if (!id) { alert('Enter bus id'); return; }
			if (ws) { try { ws.close(); } catch(e) {} }
			const scheme = (location.protocol === 'https:') ? 'wss' : 'ws';
			const url = `${scheme}://${location.host}/ws/${encodeURIComponent(id)}`;
			log('CONNECT ' + url);
			ws = new WebSocket(url);
			setStatus('Connecting...');
			ws.onopen = () => {
				setStatus('Connected');
				log('OPEN');
				document.getElementById('disconnect').disabled = false;
			};
			ws.onmessage = (ev) => {
				log('MSG: ' + ev.data);
			};
			ws.onclose = (e) => {
				setStatus('Disconnected');
				log('CLOSE code=' + e.code + ' reason=' + (e.reason || ''));
				document.getElementById('disconnect').disabled = true;
			};
			ws.onerror = (e) => {
				setStatus('Error');
				log('ERROR');
			};
		};
		document.getElementById('disconnect').onclick = () => {
			if (ws) ws.close();
		};
		</script>
	</body>
	</html>
	"""


@app.websocket("/ws-echo")
async def websocket_echo(websocket: WebSocket):
	await websocket.accept()
	await websocket.send_json({"hello": "world"})
	try:
		while True:
			data = await websocket.receive_text()
			await websocket.send_text(f"echo: {data}")
	except WebSocketDisconnect:
		pass


@app.websocket("/ws/{id_bus}")
async def websocket_bus_count(websocket: WebSocket, id_bus: str):
	await websocket.accept()
	# send initial value
	initial = get_count(id_bus)
	await websocket.send_json({"id_bus": id_bus, "count": int(initial)})

	pubsub = subscribe_count(id_bus)

	try:
		while True:
			message = await asyncio.to_thread(pubsub.get_message, True, 1.0)
			if not message or message.get("type") != "message":
				continue
			data = message.get("data")
			try:
				payload = json.loads(data)
			except Exception:
				payload = {"id_bus": id_bus, "count": get_count(id_bus)}
			await websocket.send_json(payload)
	except WebSocketDisconnect:
		pass
	finally:
		try:
			pubsub.close()
		except Exception:
			pass
