> 🇯🇵 日本語版はこちら → [README.ja.md](./README.ja.md)

# Network Simulator — Backend

Backend for **Network Simulator** — a FastAPI application that orchestrates Docker containers via Containerlab and configures FRR routing inside containers.

The backend exposes a REST API and WebSocket endpoint that the frontend uses to deploy network topologies, configure routing protocols (OSPF, RIP, BGP), and provide real-time terminal access to running containers.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
.venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API server starts at **http://localhost:8000**.  
Interactive API docs are available at **http://localhost:8000/docs** (Swagger UI).

## Tech Stack

| Tool | Purpose |
|---|---|
| **FastAPI** | REST API and WebSocket server |
| **Pydantic** | Request/response schema validation |
| **Docker SDK** | Container lifecycle management |
| **Containerlab** | Declarative container networking |
| **FRR** | OSPF, RIP, and BGP routing daemons |
| **Jinja2** | Config file generation (frr.conf, topology.clab.yml) |
| **pytest** | Unit and integration tests |

## Documentation

- **[Development Guide](./docs/development.md)** — setup, tests, Orchestrator internals, Jinja2 templates
- **[API Reference](./docs/api-reference/index.md)** — all REST endpoints, WebSocket protocol, and Pydantic schemas
