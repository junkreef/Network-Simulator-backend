> 🇯🇵 日本語版はこちら → [index.ja.md](./index.ja.md)

# API Reference — Network Simulator Backend

This document provides an overview of all API endpoints exposed by the Network Simulator backend (FastAPI). For detailed documentation on each group of endpoints, follow the links in the endpoint summary table below.

---

## Connection Details

| Property | Value |
|---|---|
| **Base URL** | `http://localhost:8000` |
| **API Version Prefix** | `/api/v1` (all REST endpoints) |
| **WebSocket Base** | `ws://localhost:8000` |
| **Authentication** | None — this is a local development tool |
| **Content-Type** | `application/json` for all request bodies |

---

## Authentication

No authentication is required. The backend is designed as a local tool and does not implement any auth mechanism. CORS is set to allow all origins (`*`).

---

## Standard Error Response Format

All error responses follow the FastAPI default format:

```json
{
  "detail": "Error description string"
}
```

For HTTP 422 (Unprocessable Entity — Pydantic validation failure), the format is:

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success — request processed correctly |
| `400` | Bad Request — invalid query parameter value |
| `422` | Unprocessable Entity — Pydantic schema validation failed |
| `500` | Internal Server Error — Docker/Containerlab/container exec failure |

---

## Complete Endpoint Summary

| Method | Endpoint | Description | Reference |
|---|---|---|---|
| `GET` | `/` | Health check | — |
| `POST` | `/api/v1/topology/deploy` | Deploy containerlab topology | [topology.md](./topology.md#post-apiv1topologydeploy) |
| `POST` | `/api/v1/topology/destroy` | Destroy running topology | [topology.md](./topology.md#post-apiv1topologydestroy) |
| `GET` | `/api/v1/topology/status` | Get runtime status of all nodes | [topology.md](./topology.md#get-apiv1topologystatus) |
| `GET` | `/api/v1/topology/state` | Get saved UI topology state | [topology.md](./topology.md#get-apiv1topologystate) |
| `POST` | `/api/v1/topology/state` | Save UI topology state | [topology.md](./topology.md#post-apiv1topologystate) |
| `DELETE` | `/api/v1/topology/state` | Reset/delete topology state | [topology.md](./topology.md#delete-apiv1topologystate) |
| `POST` | `/api/v1/nodes/{node_name}/configure` | Configure node interfaces and routing | [nodes.md](./nodes.md#post-apiv1nodesnodenameconfigure) |
| `GET` | `/api/v1/nodes/{node_name}/runtime-info` | Get runtime diagnostic info | [nodes.md](./nodes.md#get-apiv1nodesnodenameruntime-info) |
| `POST` | `/api/v1/nodes/{node_name}/interfaces/{interface_name}/state` | Set interface up/down | [nodes.md](./nodes.md#post-apiv1nodesnodenamedinterfacesinterface_namestate) |
| `WS` | `/api/v1/ws/terminal/{node_name}` | WebSocket terminal proxy | [websocket.md](./websocket.md) |

---

## Health Check

### `GET /`

Returns the server health status. No prefix — this endpoint is at the root.

**Response:**

```json
{
  "status": "healthy",
  "project": "Network Simulator",
  "version": "1.0.0"
}
```

---

## Documentation by Endpoint Group

| Document | Contents |
|---|---|
| [topology.md](./topology.md) | Deploy, destroy, status, and state endpoints for topology management |
| [nodes.md](./nodes.md) | Node configuration, runtime info, and interface state endpoints |
| [websocket.md](./websocket.md) | WebSocket terminal proxy — protocol, message format, lifecycle |
| [schemas.md](./schemas.md) | Complete Pydantic schema reference with field-level documentation |

---

## Related Documentation

- [Backend Developer Guide](../development.md)
