> 🇯🇵 日本語版はこちら → [development.ja.md](./development.ja.md)

# Backend Developer Guide

This guide covers everything you need to set up, run, test, and understand the Network Simulator backend — a FastAPI application that orchestrates Docker containers via Containerlab and configures FRR routing inside them.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.10 | Backend runtime |
| Docker | Latest | Container runtime for network nodes |
| Containerlab | Latest | Network topology orchestration |

Containerlab must be installed system-wide and accessible via `sudo containerlab` (or as root). See [Containerlab installation guide](https://containerlab.dev/install/).

The backend also requires the following custom Docker images to be built:

| Image | Path | Used for |
|---|---|---|
| `alpine-frr:latest` | `backend/docker/router/` | Router nodes (FRR) |
| `alpine-terminal:latest` | `backend/docker/terminal/` | Terminal/PC nodes |
| `alpine-switch:latest` | `backend/docker/switch/` | L2 Switch nodes |

---

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# or: .venv\Scripts\activate   (Windows)
pip install -r requirements.txt
```

### Dependencies (`requirements.txt`)

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `jinja2` | Templating for frr.conf and topology YAML |
| `docker` | Docker SDK for Python (container management) |
| `pydantic` | Request/response schema validation |
| `pydantic-settings` | Settings management via environment variables |
| `pytest` | Test runner |
| `httpx` | HTTP client for API testing |
| `websockets` | WebSocket client for integration testing |

`anyio` (used for async terminal I/O) is brought in automatically as a transitive dependency of `fastapi`/`uvicorn`.

---

## Running the Server

```bash
.venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

| Flag | Meaning |
|---|---|
| `--host 0.0.0.0` | Listen on all interfaces (required for Docker-hosted access) |
| `--port 8000` | Default backend port |
| `--reload` | Auto-restart on file changes (development mode only) |

**API documentation** (Swagger UI): http://localhost:8000/docs  
**OpenAPI schema**: http://localhost:8000/api/v1/openapi.json  
**Health check**: http://localhost:8000/

---

## Running Tests

```bash
# Run all tests
.venv/bin/pytest

# Run a specific test directory
.venv/bin/pytest tests/unit/
.venv/bin/pytest tests/integration/

# Verbose output
.venv/bin/pytest -v

# Run a specific test file
.venv/bin/pytest tests/unit/test_api.py -v
```

> **Note**: Integration tests (`tests/integration/`) require Docker to be running and the custom Docker images to be built. The `conftest.py` fixture attempts to build these images automatically.

---

## Project Structure

```
backend/
├── src/
│   └── app/
│       ├── main.py                     # FastAPI app init, CORS, router mounting, lifespan
│       ├── api/
│       │   ├── endpoints.py            # REST API routes and Pydantic request/response models
│       │   └── websocket.py            # WebSocket terminal proxy endpoint
│       ├── core/
│       │   ├── config.py               # App settings (BASE_DIR, CONFIG_DIR, TEMPLATE_DIR)
│       │   ├── orchestrator.py         # Core orchestration logic
│       │   └── default_topology.json   # Default topology loaded when no saved state exists
│       └── templates/
│           ├── frr.conf.j2             # Jinja2 template for FRR routing config
│           └── topology.clab.yml.j2    # Jinja2 template for Containerlab topology
├── tests/
│   ├── conftest.py                     # pytest fixtures and Docker image builds
│   ├── unit/
│   │   ├── test_api.py                 # Unit tests for REST endpoints
│   │   └── test_orchestrator.py        # Unit tests for the Orchestrator class
│   └── integration/
│       └── test_integration.py         # Integration tests (require Docker)
├── docker/
│   ├── router/                         # Dockerfile for alpine-frr image
│   ├── terminal/                       # Dockerfile for alpine-terminal image
│   └── switch/                         # Dockerfile for alpine-switch image
├── data/                               # Runtime-generated config files (gitignored)
├── requirements.txt
└── .venv/                              # Python virtual environment
```

---

## Configuration (`config.py`)

Settings are managed via `pydantic-settings` in `src/app/core/config.py`. All settings have sensible defaults and can be overridden with environment variables.

| Setting | Default Value | Description |
|---|---|---|
| `PROJECT_NAME` | `"Network Simulator"` | Application display name |
| `API_V1_STR` | `"/api/v1"` | URL prefix for all REST API routes |
| `BASE_DIR` | `src/app/` (absolute) | Resolved at import time from `__file__` |
| `PROJECT_ROOT` | `backend/` (absolute) | Two levels up from `BASE_DIR` |
| `CONFIG_DIR` | `{PROJECT_ROOT}/data/` | Where topology YAML and runtime configs are stored |
| `TEMPLATE_DIR` | `{BASE_DIR}/templates/` | Jinja2 template directory |

Both `CONFIG_DIR` and `TEMPLATE_DIR` are **auto-created** on import (`os.makedirs(..., exist_ok=True)`), so you do not need to create them manually.

The `data/` directory is gitignored and holds all runtime state:

```
data/
├── topology.clab.yml               # Last rendered Containerlab topology
├── topology_state.json             # Current UI editing state (React Flow)
├── topology_deployed_state.json    # State at time of last deploy
├── topology_deployed_data.json     # Internal deploy metadata (removed on destroy)
└── {topology_name}/                # Per-topology router config directories
    └── {node_name}/
        ├── daemons                 # FRR daemon enable/disable list
        ├── frr.conf                # Applied FRR routing configuration
        └── vtysh.conf              # vtysh unified config flag
```

---

## Orchestrator Class (`orchestrator.py`)

`Orchestrator` is the central class that handles all container management, configuration rendering, and state persistence. It is instantiated fresh for each API request (stateless design).

### Public Methods

| Method | Description |
|---|---|
| `deploy_topology(topology_data)` | Renders `topology.clab.yml` and runs `containerlab deploy` |
| `destroy_topology()` | Runs `containerlab destroy` and cleans up all config dirs |
| `get_topology_status()` | Runs `containerlab inspect` and returns node states |
| `configure_node(node_name, config_data)` | Applies interface/VLAN/routing config to a container |
| `get_runtime_info(node_name, info_type)` | Executes diagnostic commands inside a container |
| `configure_interface_state(node_name, interface_name, state)` | Brings an interface `up` or `down` |
| `save_topology_state(state_data, deployed?)` | Persists UI state JSON to file |
| `get_topology_state(deployed?)` | Reads persisted UI state JSON from file |
| `delete_topology_state()` | Removes state JSON files |
| `get_topology_filepath()` | Returns the absolute file path of the rendered topology.clab.yml file |

### Private/Internal Methods

| Method | Description |
|---|---|
| `_get_container_by_name(node_name)` | Resolves container by name or Containerlab naming convention |
| `_run_cmd(cmd)` | Runs subprocess, prepends `sudo` for containerlab commands |
| `_sync_vlan_interfaces(container, target_vlans)` | Syncs VLAN subinterfaces inside a container |

### Constructor

```python
orchestrator = Orchestrator()
```

- Attempts `docker.from_env()` to connect to Docker daemon. If Docker is unavailable, `self.docker_client = None` (does not raise).
- Sets up a Jinja2 `Environment` with `FileSystemLoader` pointing to `TEMPLATE_DIR`.

---

## Jinja2 Templates

### `frr.conf.j2` — FRR Routing Configuration

This template generates a complete FRR configuration file. FRR (Free Range Routing) is a Linux routing suite that supports OSPF, RIP, and BGP.

**Template variables:**

| Variable | Type | Description |
|---|---|---|
| `interfaces` | List of dicts | Physical interfaces with `name` and optional `ip_address` |
| `vlan_interfaces` | List of dicts | VLAN subinterfaces with `name` and optional `ip_address` |
| `routing` | Dict | Contains `ospf`, `rip`, `bgp` sub-dicts |
| `static_routes` | List of dicts | Each has `destination` (CIDR) and `next_hop` (IP) |

**Template structure:**

```
log file /var/log/frr/frr.log
!
# Interface blocks (physical + VLAN)
interface {name}
  ip address {ip_address}
!

# OSPF block (if routing.ospf.enabled)
router ospf
  ospf router-id {router_id}
  network {net} area {area_id}
  area {area_id} stub|nssa|...
  area {area_id} range {range}
  redistribute connected|static|rip|bgp
  default-information originate [always] [metric N]
!

# RIP block (if routing.rip.enabled)
router rip
  network {net}
  redistribute connected|static|ospf|bgp
!

# BGP block (if routing.bgp.enabled)
router bgp {as_number}
  bgp router-id {router_id}
  no bgp ebgp-requires-policy
  neighbor {ip} remote-as {remote_as}
!
  address-family ipv4 unicast
    neighbor {ip} activate
    redistribute connected|static|ospf|rip
  exit-address-family
!

# Static routes
ip route {destination} {next_hop}
```

**FRR syntax notes:**

- `!` is used as a comment/separator in FRR config
- `no bgp ebgp-requires-policy` is always included — this allows eBGP sessions without needing explicit route-policy configuration, which is important in lab environments
- Redistribution between protocols is conditional: `redistribute rip` in OSPF is only emitted if RIP is also enabled (same for bgp↔ospf cross-redistribution)

### `topology.clab.yml.j2` — Containerlab Topology

This template generates the YAML topology file consumed by `containerlab deploy`.

**Template variables:**

| Variable | Type | Description |
|---|---|---|
| `topology_name` | str | Containerlab topology name (also the namespace for container names) |
| `nodes` | List of dicts | Each has `name`, `type`, `interfaces` |
| `links` | List of dicts | Each has `endpoints` list of `"nodename:interface"` strings |
| `config_dir` | str | Absolute path to `data/` for bind mounts |

**Docker image selection by node type:**

| `node.type` | Docker image |
|---|---|
| `router` | `alpine-frr:latest` |
| `switch` | `alpine-switch:latest` |
| anything else | `alpine-terminal:latest` |

**Router bind mounts:**

For router nodes, three files from `{config_dir}/{topology_name}/{node_name}/` are mounted read-only into `/etc/frr/`:

| Host file | Container path | Purpose |
|---|---|---|
| `daemons` | `/etc/frr/daemons` | Enables/disables FRR daemons |
| `frr.conf` | `/etc/frr/frr.conf.import` | Initial FRR config (imported at startup) |
| `vtysh.conf` | `/etc/frr/vtysh.conf` | Enables integrated vtysh config |

**Exec commands:** Each node gets `ip link set dev {iface} up` for every interface in its list — this ensures interfaces are up immediately after container start.

---

## FRR Integration

### Daemons

The following FRR daemons are enabled for every router node:

| Daemon | Protocol |
|---|---|
| `zebra` | Core IP routing (required by all other daemons) |
| `bgpd` | BGP (Border Gateway Protocol) |
| `ospfd` | OSPF (Open Shortest Path First) |
| `ripd` | RIP (Routing Information Protocol) |

All other daemons (`ospf6d`, `ripngd`, `isisd`, etc.) are disabled.

### Zero-Downtime Configuration with `frr-reload.py`

When `configure_node()` is called for a router:

1. The new `frr.conf` is rendered from the Jinja2 template
2. The rendered config is written to `/etc/frr/frr.conf.new` inside the container
3. `/usr/lib/frr/frr-reload.py --reload /etc/frr/frr.conf.new` is executed

`frr-reload.py` is FRR's built-in tool for hot-reloading. It:
- Diffs the running config (from `vtysh -c "show running-config"`) against the new file
- Generates a minimal set of `vtysh` commands to transition from old to new config
- Applies only the delta — no daemon restart required

The backend waits up to 30 seconds for `vtysh` to become responsive before attempting the reload (polling `vtysh -c "write"` once per second).

### `vtysh`

`vtysh` is FRR's unified CLI. It is used for:
- Readiness checks: `vtysh -c "write"`
- Runtime queries: `vtysh -c "show ip route"`, `vtysh -c "show ip ospf neighbor"`, etc.

---

## Container Name Resolution

Containerlab names containers as `clab-{topology_name}-{node_name}`. For example, a node `r1` in topology `sim-network` becomes container `clab-sim-network-r1`.

`_get_container_by_name(node_name)` tries three resolution strategies in order:

1. **Exact match**: `container.name == node_name`
2. **Containerlab convention**: `container.name == f"clab-{topo_name}-{node_name}"` (reads `topo_name` from `topology.clab.yml`)
3. **Suffix match** (no topology file): `container.name.endswith(f"-{node_name}")`

Returns `None` if no container is found.

---

## sudo Requirement

`containerlab` commands require root privileges. `_run_cmd()` automatically prepends `sudo` when:
- The command starts with `"containerlab"`, AND
- The process is not running as root (`os.getuid() != 0`)

---

## Application Lifecycle

`main.py` registers a `lifespan` context manager that:
- **On startup**: (no-op, yields)
- **On shutdown**: calls `orchestrator.destroy_topology()` — ensures running containers are cleaned up when the server stops

CORS is configured to allow all origins (`allow_origins=["*"]`) which is appropriate for local development.

---

## Navigation

- [API Reference Overview](./api-reference/index.md)
- [Topology Endpoints](./api-reference/topology.md)
- [Node Endpoints](./api-reference/nodes.md)
- [WebSocket Terminal](./api-reference/websocket.md)
- [Pydantic Schemas](./api-reference/schemas.md)
