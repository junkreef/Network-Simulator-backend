> 🇯🇵 日本語版はこちら → [topology.ja.md](./topology.ja.md)

# Topology Endpoints

These endpoints manage the lifecycle of the network topology — deploying and destroying Docker containers via Containerlab, and persisting the UI state between sessions.

---

## `POST /api/v1/topology/deploy`

Deploys a containerlab network topology. This endpoint:

1. Sets up per-router config directories on the host (`data/{topology_name}/{node_name}/`)
2. Writes FRR daemon config files (`daemons`, `vtysh.conf`, initial `frr.conf`)
3. Renders `topology.clab.yml` from the Jinja2 template
4. Compares the rendered YAML against the previous deployment — skips if identical
5. Writes the new YAML to `data/topology.clab.yml`
6. Runs `containerlab deploy -t topology.clab.yml --reconfigure`

### Request Body

`Content-Type: application/json`  
Schema: [`TopologyDeployRequest`](./schemas.md#topologydeployrequest)

```json
{
  "name": "sim-network",
  "nodes": [
    {
      "name": "r1",
      "type": "router",
      "interfaces": ["eth1", "eth2", "eth3", "eth4"]
    },
    {
      "name": "sw1",
      "type": "switch",
      "interfaces": ["eth1", "eth2", "eth3"]
    },
    {
      "name": "pc1",
      "type": "terminal",
      "interfaces": ["eth1"]
    }
  ],
  "links": [
    { "endpoints": ["r1:eth1", "sw1:eth1"] },
    { "endpoints": ["sw1:eth2", "pc1:eth1"] }
  ]
}
```

#### Field Descriptions

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | `"sim-network"` | Topology name used as the Containerlab topology identifier and the config directory name. Container names will be `clab-{name}-{node_name}`. |
| `nodes` | array | required | List of all nodes in the topology. Each node has `name`, `type`, and `interfaces`. |
| `nodes[].name` | string | required | Unique identifier for the node (e.g., `"r1"`, `"sw1"`, `"pc1"`). |
| `nodes[].type` | string | required | Determines the Docker image: `"router"` → `alpine-frr:latest`, `"switch"` → `alpine-switch:latest`, anything else → `alpine-terminal:latest`. |
| `nodes[].interfaces` | array of strings | `[]` | Interface names assigned to this node (e.g., `["eth1", "eth2"]`). Each interface is brought up via `ip link set dev {iface} up` on container start. |
| `links` | array | required | Cable connections between node interfaces. |
| `links[].endpoints` | array of strings | required | Exactly two strings in `"nodename:interface"` format (e.g., `["r1:eth1", "sw1:eth1"]`). Defines which physical virtual port connects to which. |

### Success Response — Topology Deployed

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology deployed successfully",
  "details": {
    "name": "sim-network",
    "container_count": 3
  }
}
```

`container_count` is the number of nodes in the request (not verified against actual running containers).

### Success Response — No Change (Skipped)

HTTP `200 OK`

```json
{
  "status": "skipped",
  "message": "Topology is identical, skipping deploy",
  "details": {
    "name": "sim-network",
    "container_count": 3
  }
}
```

This response is returned when the rendered `topology.clab.yml` is byte-for-byte identical to the file from the previous deployment. This optimization avoids unnecessarily restarting containers when the topology has not changed.

### Error Response

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to deploy topology: <error detail>"
}
```

Common causes:
- Docker daemon is not running
- Required Docker image (`alpine-frr:latest`, etc.) not found
- `containerlab` is not installed or not in PATH
- Insufficient permissions for `sudo containerlab`

### Behavior Notes

- The `--reconfigure` flag passed to containerlab forces recreation of existing containers with the same name — this is necessary for topology changes.
- There is a 1-second sleep before `containerlab deploy` to allow filesystem sync after writing the YAML file.
- Router config directories are always (re)created before deployment, even on first deploy.

---

## `POST /api/v1/topology/destroy`

Destroys the currently running containerlab topology and cleans up all associated files.

### Request Body

None.

### Success Response

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology destroyed successfully"
}
```

### Success Response — No Topology File Found

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "No topology configuration found to destroy, performed fallback name-based destroy"
}
```

This response is returned when `data/topology.clab.yml` does not exist. In this case the backend attempts a fallback:  
`containerlab destroy --name sim-network --cleanup`  
If that also fails, the failure is logged but a success response is still returned.

### Error Response

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to destroy topology: <error detail>"
}
```

### Behavior Notes

- Runs `containerlab destroy -t topology.clab.yml --cleanup`. The `--cleanup` flag removes the management network and all container state.
- After containerlab destroy, the following cleanup is performed on the host:
  - All subdirectories under `data/` are deleted (e.g., `data/sim-network/`)
  - `data/topology.clab.yml` is deleted
  - `data/topology_deployed_data.json` is deleted (if present)
- `data/topology_state.json` and `data/topology_deployed_state.json` are **not** deleted by destroy — use `DELETE /api/v1/topology/state` to clear those.
- The FastAPI application's shutdown lifespan handler also calls `destroy_topology()`, so stopping the server automatically tears down the topology.

---

## `GET /api/v1/topology/status`

Returns the current runtime status of all nodes in the deployed topology by running `containerlab inspect`.

### Request Body

None.

### Success Response — Topology Running

HTTP `200 OK`

```json
{
  "topology_name": "sim-network",
  "status": "running",
  "nodes": [
    {
      "name": "r1",
      "kind": "linux",
      "state": "running",
      "ipv4_address": "172.20.20.2/24"
    },
    {
      "name": "sw1",
      "kind": "linux",
      "state": "running",
      "ipv4_address": "172.20.20.3/24"
    },
    {
      "name": "pc1",
      "kind": "linux",
      "state": "running",
      "ipv4_address": "172.20.20.4/24"
    }
  ]
}
```

#### Response Field Descriptions

| Field | Type | Description |
|---|---|---|
| `topology_name` | string | The Containerlab topology name read from `topology.clab.yml`. Empty string if not found. |
| `status` | string | `"running"` if at least one node exists in inspect output, `"stopped"` if no nodes, `"error"` if inspect failed. |
| `nodes` | array | List of node status objects from `containerlab inspect`. |
| `nodes[].name` | string | Node name as defined in the topology. |
| `nodes[].kind` | string | Containerlab node kind (always `"linux"` for this project). |
| `nodes[].state` | string | Docker container state: `"running"`, `"stopped"`, `"exited"`, etc. |
| `nodes[].ipv4_address` | string | Management IPv4 address assigned by Containerlab's management network (with prefix length). |

### Success Response — No Topology

HTTP `200 OK`

```json
{
  "topology_name": "",
  "status": "stopped",
  "nodes": []
}
```

Returned when `data/topology.clab.yml` does not exist.

### Error Response — Inspect Failed

HTTP `200 OK` (note: errors in status are returned as 200 to avoid breaking the frontend polling loop)

```json
{
  "topology_name": "",
  "status": "error",
  "message": "Command 'sudo containerlab inspect ...' returned non-zero exit status 1",
  "nodes": []
}
```

### Behavior Notes

- Runs `containerlab inspect -t topology.clab.yml --format json`.
- The inspect output is JSON with a top-level key equal to the topology name (e.g., `{"sim-network": [{...}, {...}]}`).
- **Retry logic**: The command is retried up to **5 times** with a **2-second** delay between each attempt. This handles timing gaps when containers are starting up and `containerlab inspect` may return stale or empty data.
- The topology name is first read from the file to validate which key to use from the JSON output.

---

## `GET /api/v1/topology/state`

Returns the saved UI topology state (React Flow `nodes` and `edges` arrays).

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `deployed` | boolean | `false` | `false` → reads `topology_state.json` (current editing state); `true` → reads `topology_deployed_state.json` (state at last deploy) |

### Request Body

None.

### Success Response

HTTP `200 OK`

```json
{
  "nodes": [
    {
      "id": "r1",
      "type": "routerNode",
      "position": { "x": 100, "y": 200 },
      "data": { ... }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "r1",
      "target": "sw1"
    }
  ]
}
```

The exact structure of `nodes` and `edges` matches the React Flow state format saved by the frontend. The backend treats this as an opaque JSON object.

### Behavior Notes

- **`deployed=false` fallback**: If `topology_state.json` does not exist, the backend reads `src/app/core/default_topology.json` (a built-in starter topology), copies it to `data/topology_state.json`, and returns it. This means the first load always returns a usable topology.
- **`deployed=true` — no fallback**: If `topology_deployed_state.json` does not exist, returns `{"nodes": [], "edges": []}`.
- Returns `{"nodes": [], "edges": []}` on any read error.

---

## `POST /api/v1/topology/state`

Saves the UI topology state to a JSON file for persistence between page reloads.

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `deployed` | boolean | `false` | `false` → saves to `topology_state.json`; `true` → saves to `topology_deployed_state.json` |

### Request Body

Any JSON object (React Flow topology state). The backend treats this as an opaque blob.

```json
{
  "nodes": [...],
  "edges": [...]
}
```

### Success Response

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology state saved successfully"
}
```

When `deployed=true`, the message is `"Topology state deployed successfully"`.

### Error Response

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to save topology state: <error detail>"
}
```

### Behavior Notes

- The file is written with `json.dump(..., indent=2, ensure_ascii=False)` followed by `f.flush()` and `os.fsync()` to ensure durability.
- The deploy endpoint (`POST /api/v1/topology/deploy`) itself does not automatically call this — the frontend must explicitly call `POST /api/v1/topology/state?deployed=true` after a successful deploy to record the deployed state.

---

## `DELETE /api/v1/topology/state`

Deletes both topology state files, resetting the UI to the default topology on the next load.

### Request Body

None.

### Success Response

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology state reset successfully"
}
```

### Error Response

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to reset topology state: <error detail>"
}
```

### Behavior Notes

- Deletes `data/topology_state.json` and `data/topology_deployed_state.json` if they exist.
- Does not delete `topology.clab.yml` or router config directories — use `POST /api/v1/topology/destroy` to tear down running containers.
- After deletion, the next `GET /api/v1/topology/state` call will fall back to `default_topology.json`.

---

## Navigation

- [← API Reference Index](./index.md)
- [Node Endpoints →](./nodes.md)
- [WebSocket Terminal →](./websocket.md)
- [Pydantic Schemas →](./schemas.md)
- [Backend Developer Guide](../development.md)
