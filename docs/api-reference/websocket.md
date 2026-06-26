> 🇯🇵 日本語版はこちら → [websocket.ja.md](./websocket.ja.md)

# WebSocket Terminal Proxy

The WebSocket terminal endpoint creates a bidirectional pipe between a browser-based terminal (Xterm.js) and the shell inside a running Docker container. This allows users to interact with any node in the topology directly from the browser UI.

---

## Endpoint

```
ws://localhost:8000/api/v1/ws/terminal/{node_name}
```

> **Note**: The WebSocket router is mounted under the same `/api/v1` prefix as REST endpoints. The full path is `/api/v1/ws/terminal/{node_name}`.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `node_name` | string | Node name as defined in the topology (e.g., `"r1"`, `"pc1"`). Used to locate the Docker container. |

---

## Protocol

| Property | Value |
|---|---|
| **Protocol** | Native WebSocket (RFC 6455) |
| **Message format** | Text frames (UTF-8 encoded strings) |
| **Subprotocol** | None |
| **Authentication** | None |

Messages are **text frames**. The frontend sends either:
- **JSON control messages** (for terminal resize and input events), or
- **Raw text strings** (terminal keystrokes not wrapped in JSON)

Binary frames are also accepted and forwarded directly to the container.

---

## Connection Lifecycle

```
1. Client opens WebSocket to ws://localhost:8000/api/v1/ws/terminal/{node_name}
2. Server accepts the connection (await websocket.accept())
3. Server checks Docker availability — closes with code 4001 if Docker is unavailable
4. Server locates the container for node_name — closes with code 4004 if not found
5. Server creates a Docker exec session:
     exec_create(container.id, cmd=["/bin/bash"], stdin=True, stdout=True, stderr=True, tty=True)
6. Server starts exec session with socket=True to get a raw socket
7. Server launches two concurrent async tasks via anyio.create_task_group():
     - docker_to_ws: reads from Docker socket → sends to WebSocket client
     - ws_to_docker: receives from WebSocket client → writes to Docker socket
8. Both tasks run until one of them exits (client disconnect, container exit, or error)
9. Server closes the Docker socket and logs cleanup
```

---

## Message Format

### Server → Client (Container Output)

The Docker exec API uses a framed stream format over the socket when `tty=False`. With `tty=True` (as used here), output is raw bytes without framing. However, the implementation reads the Docker multiplexed stream protocol:

- **Header**: 8 bytes. Bytes 4–7 (big-endian uint32) indicate the payload size.
- **Payload**: UTF-8 encoded terminal output.

The payload is decoded to a UTF-8 string and sent as a **WebSocket text frame**.

### Client → Server (Keystrokes / Commands)

The client sends **text frames** in one of three formats:

#### 1. Resize Event (JSON)

```json
{
  "event": "resize",
  "cols": 220,
  "rows": 50
}
```

The server calls `client.api.exec_resize(exec_id, height=rows, width=cols)` to update the TTY dimensions. This prevents output wrapping issues when the user resizes the browser window.

#### 2. Input Event (JSON)

```json
{
  "event": "input",
  "data": "ls -la\r"
}
```

The `data` field is encoded as UTF-8 and written to the Docker socket (`real_sock.sendall(data.encode("utf-8"))`).

#### 3. Raw Text (Non-JSON)

Any text that is not valid JSON is treated as raw terminal input and forwarded directly:

```
ls\r
```

This handles the case where Xterm.js sends keystrokes directly as strings without wrapping.

#### 4. Binary Frames

Binary WebSocket frames are forwarded byte-for-byte to the Docker socket via `real_sock.sendall(bytes_data)`.

---

## WebSocket Close Codes

| Code | Meaning | When Sent |
|---|---|---|
| `4001` | Docker daemon unavailable | `orchestrator.docker_client` is `None` at connection time |
| `4004` | Container not found | `_get_container_by_name(node_name)` returns `None` |
| `4005` | Failed to start terminal exec | `exec_create` or `exec_start` raised an exception |

---

## Container Name Resolution

The server uses `_get_container_by_name(node_name)` to locate the Docker container. It tries three strategies in order:

1. Exact name match: `container.name == node_name`
2. Containerlab convention: `container.name == f"clab-{topology_name}-{node_name}"` (reads topology name from `data/topology.clab.yml`)
3. Suffix match (no topology file): `container.name.endswith(f"-{node_name}")`

Returns `None` if no matching container is found.

---

## Async Implementation

The WebSocket handler uses `anyio` for concurrent async I/O:

```python
async with anyio.create_task_group() as tg:
    tg.start_soon(docker_to_ws)
    tg.start_soon(ws_to_docker)
```

Both tasks run concurrently. When either exits (due to disconnect, error, or container termination), the task group cancels the other and the handler cleans up.

Blocking Docker socket operations are offloaded to a thread pool via `anyio.to_thread.run_sync()` to avoid blocking the async event loop:

```python
header = await anyio.to_thread.run_sync(lambda: _read_exactly(8))
payload = await anyio.to_thread.run_sync(lambda: _read_exactly(size))
await anyio.to_thread.run_sync(real_sock.sendall, input_data.encode("utf-8"))
```

### `_unwrap_socket()`

The Docker SDK wraps the raw socket in several layers. `_unwrap_socket()` unwraps it by checking for `_sock`, `socket`, `_socket`, and `raw` attributes to reach the underlying OS socket:

```python
def _unwrap_socket(sock):
    real_sock = sock
    for attr in ["_sock", "socket", "_socket", "raw"]:
        if hasattr(real_sock, attr):
            val = getattr(real_sock, attr)
            if val is not None:
                real_sock = val
    return real_sock
```

The raw socket is needed to call `sendall()` directly for writing stdin to the container.

---

## Sequence Diagram

```
Browser (Xterm.js)           FastAPI WS Handler              Docker Container (/bin/bash)
       |                            |                                  |
       |-- WS connect (GET upgrade) |                                  |
       |                            |-- exec_create(/bin/bash) ------->|
       |                            |-- exec_start(socket=True) ------>|
       |<-- WS accept -------------|                                  |
       |                            |                                  |
       |              [docker_to_ws task running]                      |
       |                            |<-- Docker stream header (8B) ----|
       |                            |<-- Docker stream payload ---------|
       |<-- send_text(output) ------|                                  |
       |                            |                                  |
       |              [ws_to_docker task running]                      |
       |-- send_text(JSON input) -->|                                  |
       |                            |-- real_sock.sendall(data) ------>|
       |                            |                                  |
       |-- send_text(JSON resize) ->|                                  |
       |                            |-- exec_resize(cols, rows) ------>|
       |                            |                                  |
       |-- WS disconnect ---------->|                                  |
       |                            |-- real_sock.close() ------------>|
       |                            |                                  |
```

---

## Frontend Integration Example

```typescript
import { Terminal } from 'xterm';

const nodeName = 'r1';
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/terminal/${nodeName}`);
const terminal = new Terminal();

// Mount the terminal into a DOM element
terminal.open(document.getElementById('terminal-container'));

// Send container output to the Xterm.js terminal
ws.onmessage = (event) => {
  terminal.write(event.data);
};

// Send keystrokes from the terminal as JSON input events
terminal.onData((data) => {
  ws.send(JSON.stringify({ event: 'input', data }));
});

// Send resize events when the terminal is resized
terminal.onResize(({ cols, rows }) => {
  ws.send(JSON.stringify({ event: 'resize', cols, rows }));
});

// Handle disconnect
ws.onclose = () => {
  terminal.write('\r\n[Connection closed]\r\n');
};
```

---

## Shell and Environment

The exec session is started with `/bin/bash`:

```python
shell = "/bin/bash"
exec_inst = client.api.exec_create(container.id, cmd=[shell], stdin=True, stdout=True, stderr=True, tty=True)
```

The shell process runs inside the container with full access to all container networking tools:
- `ip`, `ping`, `traceroute`, `ss`, `netstat` (for network diagnostics)
- `vtysh` (for FRR routers — interactive FRR CLI)
- `bridge` (for switch nodes — VLAN inspection)

---

## Notes and Limitations

| Topic | Notes |
|---|---|
| **Terminal resize** | Resize is supported via JSON `{"event": "resize", "cols": N, "rows": N}` messages. The initial terminal size at exec creation is not explicitly set (defaults to Docker's default: 80×24). |
| **Multiple connections** | Multiple WebSocket clients can connect to the same node simultaneously — each creates an independent exec session. |
| **Container restart** | If the container restarts while the WebSocket is open, the exec session's pipe will break. The `docker_to_ws` loop will exit on read error, closing the connection. |
| **Security** | No authentication. Any client with network access to the backend can open a terminal to any running container. |

---

## Navigation

- [← API Reference Index](./index.md)
- [← Node Endpoints](./nodes.md)
- [Pydantic Schemas →](./schemas.md)
- [Backend Developer Guide](../development.md)
