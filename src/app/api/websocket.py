import json
import logging
import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/terminal/{node_name}")
async def websocket_terminal(websocket: WebSocket, node_name: str):
    await websocket.accept()
    
    orchestrator = Orchestrator()
    if not orchestrator.docker_client:
        await websocket.close(code=4001, reason="Docker daemon not available")
        return
        
    container = orchestrator._get_container_by_name(node_name)
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
        
        # exec_start with socket=True returns a SocketIO-like object
        docker_socket = client.api.exec_start(exec_inst["Id"], socket=True)
    except Exception as e:
        logger.error(f"Failed to start exec session: {e}")
        await websocket.close(code=4005, reason=f"Failed to start terminal: {str(e)}")
        return

    exec_id = exec_inst["Id"]
    closed = False

    async def docker_to_ws():
        nonlocal closed
        try:
            while not closed:
                def _read():
                    try:
                        # read() blocks until data is available or socket is closed
                        # docker-py socket wrapper read() function
                        return docker_socket.read(1024)
                    except Exception as e:
                        logger.debug(f"Docker socket read error/EOF: {e}")
                        return b""
                        
                data = await anyio.to_thread.run_sync(_read)
                if not data:
                    break
                
                # Decode bytes to text (replace invalid chars to prevent errors)
                text = data.decode("utf-8", errors="replace")
                await websocket.send_text(text)
        except Exception as e:
            logger.debug(f"Error in docker_to_ws loop: {e}")
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
                            client.api.exec_resize(exec_id, height=rows, width=cols)
                        elif event == "input":
                            input_data = data_json.get("data", "")
                            def _write():
                                docker_socket.write(input_data.encode("utf-8"))
                                if hasattr(docker_socket, "flush"):
                                    docker_socket.flush()
                            await anyio.to_thread.run_sync(_write)
                        else:
                            # Other JSON, write raw
                            def _write():
                                docker_socket.write(text_data.encode("utf-8"))
                            await anyio.to_thread.run_sync(_write)
                    except json.JSONDecodeError:
                        # Raw string input (terminal keystrokes)
                        def _write():
                            docker_socket.write(text_data.encode("utf-8"))
                        await anyio.to_thread.run_sync(_write)
                
                bytes_data = message.get("bytes")
                if bytes_data:
                    def _write():
                        docker_socket.write(bytes_data)
                    await anyio.to_thread.run_sync(_write)
                    
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in ws_to_docker loop: {e}")
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
            docker_socket.close()
        except Exception:
            pass
        logger.info("Terminal session cleaned up")
