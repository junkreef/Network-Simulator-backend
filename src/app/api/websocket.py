"""WebSocket terminal API proxy endpoints.

Establishes a bidirectional pipe between front-end Xterm.js client
and running Docker containers via WebSocket.
"""

import asyncio
import json
import logging
import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

def _unwrap_socket(sock):
    """Safely unwrap docker socket to get the underlying raw socket."""
    real_sock = sock
    for attr in ["_sock", "socket", "_socket", "raw"]:
        if hasattr(real_sock, attr):
            val = getattr(real_sock, attr)
            if val is not None:
                real_sock = val
    return real_sock

@router.websocket("/ws/terminal/{node_name}")
async def websocket_terminal(websocket: WebSocket, node_name: str):
    """Handles WebSocket connections to proxy terminal I/O for a specific container.

    Accepts the WebSocket connection, attaches to a bash shell inside the
    specified Docker container, and starts concurrent loops to pipe stdout/stderr
    to the client and write client stdin back to the docker exec socket.
    """
    await websocket.accept()

    orchestrator = Orchestrator()
    if not orchestrator.docker_client:
        await websocket.close(code=4001, reason="Docker daemon not available")
        return

    container = orchestrator._get_container_by_name(node_name)  # pylint: disable=protected-access
    if not container:
        await websocket.close(code=4004, reason=f"Node {node_name} not found")
        return

    client = orchestrator.docker_client

    try:
        # Determine shell. Since we installed bash in both Dockerfiles, we use /bin/bash.
        shell = "/bin/bash"

        exec_inst = client.api.exec_create(
            container.id,
            cmd=[shell],
            stdin=True,
            stdout=True,
            stderr=True,
            tty=True
        )

        docker_socket = client.api.exec_start(exec_inst["Id"], socket=True)
        real_sock = _unwrap_socket(docker_socket)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to start exec session: %s", e)
        await websocket.close(code=4005, reason=f"Failed to start terminal: {str(e)}")
        return

    exec_id = exec_inst["Id"]
    closed = False

    async def docker_to_ws():
        nonlocal closed
        try:
            while not closed:
                def _read_exactly(n):
                    try:
                        buf = b""
                        while len(buf) < n:
                            chunk = docker_socket.read(n - len(buf))
                            if not chunk:
                                break
                            buf += chunk
                        return buf
                    except Exception as e:
                        logger.debug("Docker socket read error: %s", e)
                        return b""

                # 1. Read 8-byte Docker stream header
                header = await anyio.to_thread.run_sync(lambda: _read_exactly(8))
                if not header:
                    break
                if len(header) < 8:
                    text = header.decode("utf-8", errors="replace")
                    await websocket.send_text(text)
                    break

                # 2. Extract payload size (big-endian 32-bit integer at bytes 4-7)
                size = int.from_bytes(header[4:8], byteorder="big")
                if size <= 0:
                    continue

                # 3. Read exact payload bytes
                payload = await anyio.to_thread.run_sync(lambda: _read_exactly(size))
                if not payload:
                    break

                text = payload.decode("utf-8", errors="replace")
                await websocket.send_text(text)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug("Error in docker_to_ws loop: %s", e)
        finally:
            closed = True
            logger.info("Docker to WS loop finished")

    async def ws_to_docker():
        nonlocal closed
        try:
            while not closed:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break

                text_data = message.get("text")
                if text_data:
                    try:
                        # Check if message is a control JSON event
                        data_json = json.loads(text_data)
                        event = data_json.get("event")
                        if event == "resize":
                            cols = data_json.get("cols", 80)
                            rows = data_json.get("rows", 24)
                            await anyio.to_thread.run_sync(
                                lambda: client.api.exec_resize(exec_id, height=rows, width=cols)
                            )
                        elif event == "input":
                            input_data = data_json.get("data", "")
                            print(f"DEBUG INPUT: {repr(input_data)}", flush=True)
                            await anyio.to_thread.run_sync(
                                real_sock.sendall, input_data.encode("utf-8")
                            )
                        else:
                            # Other JSON, write raw
                            print(f"DEBUG OTHER JSON INPUT: {repr(text_data)}", flush=True)
                            await anyio.to_thread.run_sync(
                                real_sock.sendall, text_data.encode("utf-8")
                            )
                    except json.JSONDecodeError:
                        # Raw string input (terminal keystrokes)
                        print(f"DEBUG RAW TEXT INPUT: {repr(text_data)}", flush=True)
                        await anyio.to_thread.run_sync(
                            real_sock.sendall, text_data.encode("utf-8")
                        )

                bytes_data = message.get("bytes")
                if bytes_data:
                    print(f"DEBUG BYTES INPUT: {repr(bytes_data)}", flush=True)
                    await anyio.to_thread.run_sync(real_sock.sendall, bytes_data)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in ws_to_docker loop: %s", e)
        finally:
            closed = True
            logger.info("WS to Docker loop finished")

    # Run both concurrent loops
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(docker_to_ws)
            tg.start_soon(ws_to_docker)
    finally:
        closed = True
        try:
            real_sock.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        logger.info("Terminal session cleaned up")

