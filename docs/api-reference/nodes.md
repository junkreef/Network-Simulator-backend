> 🇯🇵 日本語版はこちら → [nodes.ja.md](./nodes.ja.md)

# Node Endpoints

These endpoints configure individual network nodes (routers, switches, terminals), retrieve runtime diagnostic information from inside containers, and control interface administrative state.

---

## `POST /api/v1/nodes/{node_name}/configure`

Applies a full configuration to a specific node. The behavior differs by node type:

- **Router** (`alpine-frr`): Renders `frr.conf` via Jinja2 template and applies it zero-downtime using `frr-reload.py` inside the container.
- **L2 Switch** (`alpine-switch`): Creates a VLAN-filtering Linux bridge (`br0`) and maps ports to access or trunk mode.
- **Terminal** (`alpine-terminal`): Directly applies IP addresses and default gateway via `ip` commands.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `node_name` | string | Node name as defined in the topology (e.g., `"r1"`, `"sw1"`, `"pc1"`) |

### Request Body

`Content-Type: application/json`  
Schema: [`RouterConfigureRequest`](./schemas.md#routerconfigurerequest)

#### Full Request Body Example (Router)

```json
{
  "interfaces": [
    {
      "name": "eth1",
      "ip_address": "192.168.1.1/24",
      "vlan_mode": null,
      "vlan_id": null,
      "vlan_ids": null
    },
    {
      "name": "eth2",
      "ip_address": "10.0.0.1/30",
      "vlan_mode": null,
      "vlan_id": null,
      "vlan_ids": null
    }
  ],
  "vlan_interfaces": [
    {
      "name": "eth1.10",
      "parent": "eth1",
      "vlan_id": 10,
      "ip_address": "10.10.10.1/24"
    }
  ],
  "routing": {
    "ospf": {
      "enabled": true,
      "router_id": "1.1.1.1",
      "areas": [
        {
          "area_id": "0.0.0.0",
          "networks": ["192.168.1.0/24", "10.0.0.0/30"],
          "interfaces": [],
          "ranges": ["10.0.0.0/8"],
          "area_type": "normal"
        },
        {
          "area_id": "0.0.0.1",
          "networks": ["10.10.10.0/24"],
          "interfaces": [],
          "ranges": [],
          "area_type": "stub"
        }
      ],
      "redistribute": {
        "connected": false,
        "static": true,
        "ospf": false,
        "rip": false,
        "bgp": false
      },
      "default_information_originate": {
        "enabled": true,
        "always": false,
        "metric": null
      }
    },
    "rip": {
      "enabled": false,
      "networks": [],
      "redistribute": {
        "connected": false,
        "static": false,
        "ospf": false,
        "bgp": false
      }
    },
    "bgp": {
      "enabled": false,
      "as_number": 65001,
      "router_id": "1.1.1.1",
      "neighbors": [
        {
          "ip_address": "192.168.1.2",
          "remote_as": 65002
        }
      ],
      "redistribute": {
        "connected": false,
        "static": false,
        "ospf": false,
        "rip": false
      }
    }
  },
  "gateway": "192.168.1.254",
  "static_routes": [
    {
      "destination": "172.16.0.0/16",
      "next_hop": "192.168.1.254"
    }
  ]
}
```

#### Top-Level Field Descriptions

| Field | Type | Default | Description |
|---|---|---|---|
| `interfaces` | List[InterfaceConfig] | `[]` | Physical interface configurations. For routers, these generate `interface` stanzas in `frr.conf`. For terminals, IP addresses are applied directly via `ip addr add`. |
| `vlan_interfaces` | List[VlanInterfaceConfig] | `[]` | VLAN subinterface configurations (e.g., `eth1.10`). Subinterfaces are created via `ip link add link {parent} name {name} type vlan id {id}` and brought up. |
| `routing` | RoutingConfig \| null | `null` | Dynamic routing protocol configurations. Only used for router nodes. |
| `gateway` | string \| null | `null` | Default gateway IP address. **For routers**: converted to a `0.0.0.0/0` static route in `frr.conf` (if no `0.0.0.0/0` entry already exists in `static_routes`). **For terminals**: applied via `ip route add default via {gateway}`. |
| `static_routes` | List[StaticRouteConfig] | `[]` | Static route entries added to `frr.conf` as `ip route {destination} {next_hop}`. |

#### `interfaces[].vlan_mode`, `vlan_id`, `vlan_ids` (Switch-Specific)

For switch nodes, the `vlan_mode`, `vlan_id`, and `vlan_ids` fields on each interface control Linux bridge VLAN filtering:

| Field | Type | Default | Description |
|---|---|---|---|
| `vlan_mode` | string \| null | `null` (treated as `"access"`) | Port mode: `"access"` or `"trunk"` |
| `vlan_id` | int \| null | `null` | For `"access"` mode: single VLAN ID (configured with `pvid` and `untagged` flags) |
| `vlan_ids` | List[int] \| null | `null` | For `"trunk"` mode: list of allowed VLAN IDs (each added without `untagged`) |

#### `routing.ospf` Field Descriptions

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Enables the OSPF `router ospf` block in `frr.conf` |
| `router_id` | string \| null | `null` | OSPF router ID in dotted decimal notation (e.g., `"1.1.1.1"`). Omitted if null. |
| `areas` | List[OspfAreaConfig] | `[]` | List of OSPF areas. Each area configures which networks are advertised and the area type. |
| `areas[].area_id` | string | required | Area identifier in dotted decimal (e.g., `"0.0.0.0"` for backbone area 0). |
| `areas[].networks` | List[str] | `[]` | Networks to advertise in this area (`network {net} area {area_id}`). |
| `areas[].ranges` | List[str] | `[]` | Route summarization ranges (`area {area_id} range {range}`). |
| `areas[].area_type` | string | `"normal"` | Area type: `"normal"`, `"stub"`, `"totally-stub"`, `"nssa"`, `"totally-nssa"`. Maps to FRR area commands. |
| `redistribute.connected` | bool | `false` | `redistribute connected` in OSPF |
| `redistribute.static` | bool | `false` | `redistribute static` in OSPF |
| `redistribute.rip` | bool | `false` | `redistribute rip` (only emitted if RIP is also enabled) |
| `redistribute.bgp` | bool | `false` | `redistribute bgp` (only emitted if BGP is also enabled) |
| `default_information_originate.enabled` | bool | `false` | `default-information originate` |
| `default_information_originate.always` | bool | `false` | Appends `always` — advertises default route even if none exists locally |
| `default_information_originate.metric` | int \| null | `null` | Appends `metric {N}` to override the default metric |

#### `routing.rip` Field Descriptions

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Enables the `router rip` block in `frr.conf` |
| `networks` | List[str] | `[]` | Networks to participate in RIP (`network {net}`) |
| `redistribute.connected` | bool | `false` | `redistribute connected` in RIP |
| `redistribute.static` | bool | `false` | `redistribute static` in RIP |
| `redistribute.ospf` | bool | `false` | `redistribute ospf` (only emitted if OSPF is also enabled) |
| `redistribute.bgp` | bool | `false` | `redistribute bgp` (only emitted if BGP is also enabled) |

#### `routing.bgp` Field Descriptions

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Enables the `router bgp {as_number}` block in `frr.conf` |
| `as_number` | int \| null | `null` | This router's AS number |
| `router_id` | string \| null | `null` | BGP router ID in dotted decimal |
| `neighbors` | List[BgpNeighborConfig] | `[]` | BGP peer list. Each generates `neighbor {ip} remote-as {as}` and `neighbor {ip} activate` in the `address-family ipv4 unicast` block. |
| `redistribute.connected` | bool | `false` | `redistribute connected` in BGP's `address-family ipv4 unicast`. **Note**: if no `redistribute` is specified at all, `redistribute connected` is added by default. |
| `redistribute.static` | bool | `false` | `redistribute static` in BGP |
| `redistribute.ospf` | bool | `false` | `redistribute ospf` (only emitted if OSPF is also enabled) |
| `redistribute.rip` | bool | `false` | `redistribute rip` (only emitted if RIP is also enabled) |

`no bgp ebgp-requires-policy` is always included, allowing eBGP sessions without route policies.

### Switch-Specific Request Body Example

For a switch node, only `interfaces` with `vlan_mode`/`vlan_id`/`vlan_ids` are relevant. The `routing` and `vlan_interfaces` fields are ignored.

```json
{
  "interfaces": [
    {
      "name": "eth1",
      "vlan_mode": "access",
      "vlan_id": 10
    },
    {
      "name": "eth2",
      "vlan_mode": "trunk",
      "vlan_ids": [10, 20, 30]
    },
    {
      "name": "eth3",
      "vlan_mode": "access",
      "vlan_id": 20
    }
  ]
}
```

**Switch configuration process:**

1. A Linux bridge `br0` is created with VLAN filtering enabled, no STP, and forward delay 0:  
   `ip link add name br0 type bridge vlan_filtering 1 forward_delay 0 stp_state 0`
2. `br0` is brought up.
3. For each interface:
   - Interface is added to the bridge as a member: `ip link set dev {iface} master br0`
   - Interface is brought up: `ip link set dev {iface} up`
   - Default VLAN 1 is removed: `bridge vlan del dev {iface} vid 1`
   - **Access mode**: `bridge vlan add dev {iface} vid {vlan_id} pvid untagged`
   - **Trunk mode**: For each VLAN ID: `bridge vlan add dev {iface} vid {vid}`

### Terminal-Specific Request Body Example

For terminal nodes, only `interfaces` (with `ip_address`) and `gateway` are used.

```json
{
  "interfaces": [
    {
      "name": "eth1",
      "ip_address": "192.168.1.10/24"
    }
  ],
  "gateway": "192.168.1.1"
}
```

**Terminal configuration process:**

1. For each interface with an IP: flush existing addresses, then `ip addr add {ip} dev {iface}` and `ip link set dev {iface} up`.
2. If gateway is specified: `ip route del default` then `ip route add default via {gateway}`.

### Success Response

HTTP `200 OK`

**Router:**
```json
{
  "status": "success",
  "output": "Configuration applied successfully via frr-reload.py"
}
```

The `output` field contains the actual output from `frr-reload.py` if it produces output, or the default message shown above.

**Switch:**
```json
{
  "status": "success",
  "output": "L2 Switch configured successfully with VLAN filtering"
}
```

**Terminal:**
```json
{
  "status": "success",
  "output": "Terminal interfaces and routing configured successfully"
}
```

### Error Response

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to configure node r1: <error detail>"
}
```

Common causes:
- Container not found (topology not deployed, or node name mismatch)
- `frr-reload.py` returned a non-zero exit code (FRR config syntax error)
- vtysh did not become responsive within 30 seconds

### Behavior Notes — Router Configuration Details

1. `_sync_vlan_interfaces()` is called first to add/remove VLAN subinterfaces on the Linux kernel side.
2. VLAN interface IPs are applied directly to the kernel regardless of FRR config (required so kernel routing works alongside FRR).
3. The backend waits for `vtysh -c "write"` to return exit code 0 (up to 30 attempts, 1s apart) before applying the frr.conf.
4. The new config is written to `/etc/frr/frr.conf.new` inside the container, then `frr-reload.py --reload /etc/frr/frr.conf.new` applies only the delta.
5. The temp file `/etc/frr/frr.conf.new` is deleted after reload.
6. On success, the rendered `frr.conf` is also written to the host file (`data/{topo_name}/{node_name}/frr.conf`) for persistence across container restarts.

---

## `GET /api/v1/nodes/{node_name}/runtime-info`

Retrieves runtime diagnostic information from inside a node's container by executing CLI commands.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `node_name` | string | Node name as defined in the topology |

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `type` | string | yes | Type of runtime info to retrieve. Must be one of the values listed below. |

#### Valid `type` Values

| `type` | Router command | Terminal/Switch command |
|---|---|---|
| `routing_table` | `vtysh -c "show ip route"` | `ip route show` |
| `arp_table` | `ip neighbor show` | `ip neighbor show` |
| `ospf_neighbors` | `vtysh -c "show ip ospf neighbor"` | ❌ Error: routers only |
| `bgp_neighbors` | `vtysh -c "show ip bgp summary"` | ❌ Error: routers only |
| `rip_status` | `vtysh -c "show ip rip"` | ❌ Error: routers only |

Node type is determined by checking whether `"frr"` is in the container image name — `alpine-frr:latest` images are treated as routers.

### Request Body

None.

### Success Response

HTTP `200 OK`

```json
{
  "node_name": "r1",
  "info_type": "routing_table",
  "raw_output": "Codes: K - kernel route, C - connected, S - static, R - RIP,\n       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,\n       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,\n       F - PBR, f - OpenFabric,\n       > - selected route, * - FIB route, q - queued, r - rejected, b - backup\n\nO   10.0.0.0/30 [110/10] is directly connected, eth2, weight 1, 00:05:10\nC>* 10.0.0.0/30 is directly connected, eth2, 00:05:10\nO>* 10.10.10.0/24 [110/20] via 10.0.0.2, eth2, weight 1, 00:03:15\nC>* 192.168.1.0/24 is directly connected, eth1, 00:05:10\nS>* 0.0.0.0/0 [1/0] via 192.168.1.254, eth1, weight 1, 00:05:10"
}
```

```json
{
  "node_name": "r1",
  "info_type": "ospf_neighbors",
  "raw_output": "\nNeighbor ID     Pri State           Dead Time Address         Interface            RXmtL RqstL DBsmL\n2.2.2.2           1 Full/Backup      00:00:38 10.0.0.2        eth2:10.0.0.1            0     0     0\n"
}
```

```json
{
  "node_name": "pc1",
  "info_type": "routing_table",
  "raw_output": "default via 192.168.1.1 dev eth1\n192.168.1.0/24 dev eth1 proto kernel scope link src 192.168.1.10\n"
}
```

#### Response Field Descriptions

| Field | Type | Description |
|---|---|---|
| `node_name` | string | The node name from the path parameter |
| `info_type` | string | The `type` query parameter value |
| `raw_output` | string | Raw stdout from the command executed inside the container |

### Error Response — Invalid Type

HTTP `400 Bad Request`

```json
{
  "detail": "Invalid type. Must be one of routing_table, arp_table, ospf_neighbors, bgp_neighbors, rip_status"
}
```

### Error Response — Protocol Not Available on Terminal

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to get runtime info for pc1: OSPF neighbors only available on routers"
}
```

### Error Response — Command Failed

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to get runtime info for r1: Failed to execute command vtysh -c show ip route: ..."
}
```

---

## `POST /api/v1/nodes/{node_name}/interfaces/{interface_name}/state`

Sets the administrative state of a specific network interface inside a container by running `ip link set dev {interface_name} {up|down}`.

This is equivalent to connecting or disconnecting a cable in a physical network — the interface remains configured but sends/receives no traffic when `down`.

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `node_name` | string | Node name as defined in the topology (e.g., `"r1"`) |
| `interface_name` | string | Interface name on the node (e.g., `"eth1"`) |

### Query Parameters

| Parameter | Type | Required | Validation | Description |
|---|---|---|---|---|
| `state` | string | yes | Must match `^(up\|down)$` | Target interface state |

### Request Body

None.

### Success Response

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Interface eth1 set to down successfully",
  "details": {
    "node_name": "r1",
    "interface_name": "eth1",
    "state": "down"
  }
}
```

### Error Response — Invalid State Parameter

HTTP `422 Unprocessable Entity` (Pydantic/FastAPI query validation)

```json
{
  "detail": [
    {
      "loc": ["query", "state"],
      "msg": "string does not match regex \"^(up|down)$\"",
      "type": "value_error.str.regex"
    }
  ]
}
```

### Error Response — Container Not Found

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to configure interface state for r1 eth1: Container for node r1 not found"
}
```

### Error Response — Command Failed

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to configure interface state for r1 eth1: Failed to set interface eth1 to down: Cannot find device \"eth1\""
}
```

### Behavior Notes

- Runs `ip link set dev {interface_name} {state}` directly inside the container.
- For routers running FRR: the `zebra` daemon will detect the link state change and update the routing table accordingly. An interface brought `down` will remove its directly-connected routes.
- OSPF/BGP sessions on that interface will also go down, triggering neighbor loss events and route reconvergence.

---

## Navigation

- [← API Reference Index](./index.md)
- [← Topology Endpoints](./topology.md)
- [WebSocket Terminal →](./websocket.md)
- [Pydantic Schemas →](./schemas.md)
- [Backend Developer Guide](../development.md)
