from __future__ import annotations

import argparse
import asyncio
import json
from uuid import uuid4

import websockets


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send transcript input to the Mums Can Build harness.")
    parser.add_argument("text", help="Transcript text to send.")
    parser.add_argument("--url", default="ws://127.0.0.1:8000", help="FastAPI server WebSocket base URL.")
    parser.add_argument("--session", default=f"local-{uuid4().hex[:8]}", help="Session id.")
    parser.add_argument("--worker", choices=["mock", "real"], default="mock", help="Worker mode.")
    parser.add_argument("--workspace", default=None, help="Workspace for real Codex runs.")
    args = parser.parse_args()

    async with websockets.connect(f"{args.url}/ws/{args.session}") as websocket:
        print(await websocket.recv())
        await websocket.send(
            json.dumps(
                {
                    "type": "user.transcript",
                    "text": args.text,
                    "worker": args.worker,
                    "workspace": args.workspace,
                }
            )
        )
        while True:
            message = json.loads(await websocket.recv())
            print(json.dumps(message, indent=2))
            if message["type"] in {"codex.done", "pm.question", "session.error"}:
                break


if __name__ == "__main__":
    asyncio.run(main())
