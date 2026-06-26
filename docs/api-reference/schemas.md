> 🇯🇵 日本語版はこちら → [schemas.ja.md](./schemas.ja.md)

# Pydantic Schema Reference

All Pydantic models used in the Network Simulator backend are defined in `src/app/api/endpoints.py`. These models serve as the authoritative schema for request body validation and serialization.

This document covers every model in detail, including field types, defaults, and behavioral notes.

---

## Topology Models

### `NodeSchema`

**Purpose**: Represents a single network node in the topology.

**Used in**: [`TopologyDeployRequest`](#topologydeployrequest)

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Unique node identifier within the topology (e.g., `"r1"`, `"sw1"`, `"pc1"`). Used as the node name in Containerlab and as the container name suffix. |
| `type` | `str` | required | Node type string. Determines which Docker image is used: `"router"` → `alpine-frr:latest`, `"switch"` → `alpine-switch:latest`, any other value → `alpine-terminal:latest`. Also used to determine configuration behavior in `configure_node()`. |
| `interfaces` | `List[str]` | `[]` | List of interface names (e.g., `["eth1", "eth2"]`). Each interface receives `ip link set dev {iface} up` on container startup via Containerlab `exec`. |

---

### `LinkSchema`

**Purpose**: Represents a physical cable connection between two node interfaces.

**Used in**: [`TopologyDeployRequest`](#topologydeployrequest)

| Field | Type | Default | Description |
|---|---|---|---|
| `endpoints` | `List[str]` | required | Exactly two strings in `"nodename:interface"` format (e.g., `["r1:eth1", "sw1:eth1"]`). The order determines which interface on each side is connected. Containerlab creates a virtual Ethernet pair between the two endpoints. |

---

### `TopologyDeployRequest`

**Purpose**: Full topology deployment request body.

**Used in**: `POST /api/v1/topology/deploy`

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"sim-network"` | Topology identifier. Used as: Containerlab topology name (appears in `name:` field of `topology.clab.yml`), container name prefix (`clab-{name}-{node_name}`), and config directory name (`data/{name}/{node_name}/`). |
| `nodes` | `List[NodeSchema]` | required | All nodes in the topology. |
| `links` | `List[LinkSchema]` | required | All links (cables) between node interfaces. |

---

## Node Configuration Models

### `InterfaceConfig`

**Purpose**: Configuration for a single physical network interface. Used for both routers (generates FRR `interface` stanzas) and switches (controls VLAN bridge membership).

**Used in**: [`RouterConfigureRequest`](#routerconfigurerequest)

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Interface name as it appears inside the Linux container (e.g., `"eth1"`, `"eth2"`). |
| `ip_address` | `Optional[str]` | `None` | IP address in CIDR notation (e.g., `"192.168.1.1/24"`). For routers, generates `ip address {value}` in the `interface` block of `frr.conf`. For terminals, applied via `ip addr add`. Ignored for switch nodes. |
| `vlan_mode` | `Optional[str]` | `None` | **Switch nodes only.** Port VLAN mode: `"access"` (single untagged VLAN) or `"trunk"` (multiple tagged VLANs). If `None`, defaults to `"access"` behavior. |
| `vlan_id` | `Optional[int]` | `None` | **Switch access mode only.** Single VLAN ID for this port (e.g., `10`). Configured with the `pvid` and `untagged` flags in the Linux bridge. |
| `vlan_ids` | `Optional[List[int]]` | `None` | **Switch trunk mode only.** List of VLAN IDs allowed on this trunk port (e.g., `[10, 20, 30]`). Each ID is added without the `untagged` flag. |

---

### `VlanInterfaceConfig`

**Purpose**: Configuration for a VLAN subinterface (802.1Q tagged subinterface). These are Linux kernel VLAN interfaces created via `ip link add ... type vlan`.

**Used in**: [`RouterConfigureRequest`](#routerconfigurerequest)

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Subinterface name (e.g., `"eth1.10"`). Naming convention is `{parent}.{vlan_id}`. |
| `parent` | `str` | required | Parent physical interface (e.g., `"eth1"`). The subinterface carries tagged traffic for the specified VLAN over this physical link. |
| `vlan_id` | `int` | required | VLAN ID (1–4094). Used in `ip link add ... type vlan id {vlan_id}`. Must match the VLAN tag in the traffic flow. |
| `ip_address` | `Optional[str]` | `None` | IP address in CIDR notation for the subinterface. Applied both via `ip addr add` (kernel) and in the `frr.conf` `interface` block (for FRR routing). |

---

## OSPF Models

### `OspfAreaConfig`

**Purpose**: OSPF area configuration — defines which networks belong to an area and how the area behaves (normal, stub, NSSA, etc.).

**Used in**: [`OspfConfig`](#ospfconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `area_id` | `str` | required | Area identifier in dotted decimal notation. `"0.0.0.0"` is the backbone area (Area 0). Non-backbone areas must connect to Area 0 directly or via virtual links. |
| `networks` | `List[str]` | `[]` | Networks advertised in this area. Each generates `network {net} area {area_id}` in the `router ospf` block. Format: CIDR (e.g., `"192.168.1.0/24"`). |
| `interfaces` | `Optional[List[str]]` | `[]` | Interface names (informational only — not directly used in template rendering). |
| `ranges` | `Optional[List[str]]` | `[]` | Route summarization ranges. Each generates `area {area_id} range {range}`. Used to aggregate multiple specific routes into one summary advertisement at area boundaries. |
| `area_type` | `Optional[str]` | `"normal"` | Area type: `"normal"` (no special handling), `"stub"` → `area {id} stub`, `"totally-stub"` → `area {id} stub no-summary`, `"nssa"` → `area {id} nssa`, `"totally-nssa"` → `area {id} nssa no-summary`. |

**Area type notes**:
- **Stub**: Does not accept Type 5 LSAs (external routes). Useful for reducing routing table size at the edge.
- **Totally-stub**: Stub + does not accept Type 3 LSAs (summary routes). Only a default route enters the area.
- **NSSA**: Not-So-Stubby Area — allows limited external route importation via Type 7 LSAs.
- **Totally-NSSA**: Combines NSSA and totally-stub behavior.

---

### `RedistributionConfig`

**Purpose**: Controls which routes from other sources are imported into a routing protocol. The same model is reused for OSPF, RIP, and BGP redistribution — though not all fields are applicable in all contexts.

**Used in**: [`OspfConfig`](#ospfconfig), [`RipConfig`](#ripconfig), [`BgpConfig`](#bgpconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `connected` | `Optional[bool]` | `False` | Redistribute directly connected routes (subnets of configured interfaces). |
| `static` | `Optional[bool]` | `False` | Redistribute static routes configured in `frr.conf` via `ip route`. |
| `ospf` | `Optional[bool]` | `False` | Redistribute OSPF-learned routes. **Conditional**: only emitted if OSPF is also enabled. Used in RIP and BGP config. Not applicable within OSPF itself (field is present in the shared model but not rendered for OSPF→OSPF redistribution). |
| `rip` | `Optional[bool]` | `False` | Redistribute RIP-learned routes. **Conditional**: only emitted if RIP is also enabled. Used in OSPF and BGP config. |
| `bgp` | `Optional[bool]` | `False` | Redistribute BGP-learned routes. **Conditional**: only emitted if BGP is also enabled. Used in OSPF and RIP config. |

> **Conditional redistribution**: The template only emits `redistribute {protocol}` for cross-protocol redistribution when the source protocol is also enabled. For example, `redistribute rip` in OSPF is skipped if `routing.rip.enabled` is `false`. This prevents invalid FRR config.

---

### `OspfDefaultInformationOriginate`

**Purpose**: Controls OSPF default route advertisement — whether this router advertises a `0.0.0.0/0` default route into the OSPF domain.

**Used in**: [`OspfConfig`](#ospfconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` | If `true`, adds `default-information originate` to the `router ospf` block. |
| `always` | `Optional[bool]` | `False` | If `true`, appends `always` — the default route is advertised even if this router has no default route in its own routing table. Without `always`, the router only advertises the default if it has one itself. |
| `metric` | `Optional[int]` | `None` | If set, appends `metric {N}` to override the default OSPF metric for the default route. |

**FRR syntax produced**:
```
default-information originate
default-information originate always
default-information originate always metric 100
```

---

### `OspfConfig`

**Purpose**: Full OSPF routing configuration for a router node.

**Used in**: [`RoutingConfig`](#routingconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` | Master switch. If `false`, the entire `router ospf` block is omitted from `frr.conf`. |
| `router_id` | `Optional[str]` | `None` | OSPF router ID (dotted decimal, e.g., `"1.1.1.1"`). Strongly recommended — without an explicit router ID, FRR selects one automatically from the highest loopback/interface IP, which can change unpredictably. |
| `areas` | `List[OspfAreaConfig]` | `[]` | OSPF area configurations. |
| `redistribute` | `Optional[RedistributionConfig]` | `None` | Routes to import into OSPF from other sources. |
| `default_information_originate` | `Optional[OspfDefaultInformationOriginate]` | `None` | Default route advertisement into OSPF. |

---

## RIP Models

### `RipConfig`

**Purpose**: RIP (Routing Information Protocol) configuration. RIP is a distance-vector protocol, simpler than OSPF but less scalable. FRR uses RIPv2 by default.

**Used in**: [`RoutingConfig`](#routingconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` | Master switch. If `false`, the `router rip` block is omitted. |
| `networks` | `List[str]` | `[]` | Networks to activate RIP on. Each generates `network {net}`. RIP will send and receive updates on interfaces whose addresses fall within these networks. |
| `redistribute` | `Optional[RedistributionConfig]` | `None` | Routes to import into RIP. Note: `rip` field in `RedistributionConfig` is not applicable here (cannot redistribute RIP into itself). |

---

## BGP Models

### `BgpNeighborConfig`

**Purpose**: A single BGP peer (neighbor) configuration.

**Used in**: [`BgpConfig`](#bgpconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `ip_address` | `str` | required | The neighbor's IP address. Generates `neighbor {ip_address} remote-as {remote_as}` in the BGP config and `neighbor {ip_address} activate` in the `address-family ipv4 unicast` block. |
| `remote_as` | `int` | required | The neighbor's AS number. If this differs from `as_number`, the session is eBGP (external BGP). If they are the same, it is iBGP (internal BGP). |

---

### `BgpConfig`

**Purpose**: BGP (Border Gateway Protocol) configuration. BGP is the inter-domain routing protocol used on the internet. In this simulator, it can be used to connect routers in different Autonomous Systems.

**Used in**: [`RoutingConfig`](#routingconfig)

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `False` | Master switch. If `false`, the `router bgp` block is omitted. |
| `as_number` | `Optional[int]` | `None` | This router's Autonomous System number. Required when `enabled=true`. Appears in `router bgp {as_number}`. |
| `router_id` | `Optional[str]` | `None` | BGP router ID (dotted decimal). If not set, FRR will select one automatically. |
| `neighbors` | `List[BgpNeighborConfig]` | `[]` | BGP peers. |
| `redistribute` | `Optional[RedistributionConfig]` | `None` | Routes to import into BGP's `address-family ipv4 unicast`. **Special behavior**: if `redistribute` is `None` or all flags are `false`, the template defaults to `redistribute connected` — ensuring the router's own interfaces are always reachable via BGP. |

**Always-included FRR directive**: `no bgp ebgp-requires-policy` — this disables FRR's default requirement for explicit route-map policies on eBGP sessions. Without this, eBGP neighbors would not exchange any routes unless route policies are configured.

---

## Composite Models

### `RoutingConfig`

**Purpose**: Container grouping all three dynamic routing protocol configurations. All fields are optional; omitting a protocol is equivalent to setting `enabled: false`.

**Used in**: [`RouterConfigureRequest`](#routerconfigurerequest)

| Field | Type | Default | Description |
|---|---|---|---|
| `ospf` | `Optional[OspfConfig]` | `None` | OSPF configuration. If `None`, OSPF is disabled. |
| `rip` | `Optional[RipConfig]` | `None` | RIP configuration. If `None`, RIP is disabled. |
| `bgp` | `Optional[BgpConfig]` | `None` | BGP configuration. If `None`, BGP is disabled. |

---

### `StaticRouteConfig`

**Purpose**: A single static route entry. Static routes are added directly to the FRR routing table via `ip route` directives in `frr.conf`.

**Used in**: [`RouterConfigureRequest`](#routerconfigurerequest)

| Field | Type | Default | Description |
|---|---|---|---|
| `destination` | `str` | required | Destination network in CIDR notation (e.g., `"172.16.0.0/16"`, `"0.0.0.0/0"`). |
| `next_hop` | `str` | required | Next-hop IP address (e.g., `"192.168.1.254"`). The packet is forwarded to this IP address for matching destinations. |

---

### `RouterConfigureRequest`

**Purpose**: The main request body for the node configuration endpoint. Used for all node types (routers, switches, and terminals), though the applicable fields differ by type.

**Used in**: `POST /api/v1/nodes/{node_name}/configure`

| Field | Type | Default | Description |
|---|---|---|---|
| `interfaces` | `List[InterfaceConfig]` | `[]` | Physical interface configurations. |
| `vlan_interfaces` | `List[VlanInterfaceConfig]` | `[]` | VLAN subinterface configurations. Processed before `frr.conf` rendering. Subinterfaces are synced (added/removed) on the Linux kernel side. |
| `routing` | `Optional[RoutingConfig]` | `None` | Dynamic routing protocol configurations. Used only for router nodes. |
| `gateway` | `Optional[str]` | `None` | Default gateway IP address. **Type coercion for routers**: if `gateway` is provided and no `0.0.0.0/0` entry exists in `static_routes`, the gateway is automatically appended as `{"destination": "0.0.0.0/0", "next_hop": gateway}`. |
| `static_routes` | `List[StaticRouteConfig]` | `[]` | Static routes. |

---

## Type Coercion and Special Behaviors

### Gateway → Static Route Coercion (Routers)

When `gateway` is provided in a router configuration, the orchestrator automatically converts it to a static default route:

```python
if gateway:
    if not any(r.get("destination") in ("0.0.0.0/0", "0.0.0.0") for r in static_routes):
        static_routes.append({"destination": "0.0.0.0/0", "next_hop": gateway})
```

This produces the following in `frr.conf`:

```
ip route 0.0.0.0/0 192.168.1.254
```

If a `0.0.0.0/0` entry already exists in `static_routes`, the gateway is not added again (no duplicate default routes).

For terminal nodes, `gateway` is applied directly via `ip route add default via {gateway}` — no coercion to `static_routes`.

### BGP Default Redistribution

If `routing.bgp.redistribute` is `None` or all redistribution flags are `false`, the `frr.conf.j2` template defaults to emitting `redistribute connected` in the BGP `address-family ipv4 unicast` block. This ensures the router's own connected prefixes are always advertised to BGP neighbors even without explicit redistribution config.

### VLAN Subinterface Synchronization

The `_sync_vlan_interfaces()` method performs a diff between existing kernel VLAN interfaces (parsed from `ip link show`) and the target list in `vlan_interfaces`:
- Interfaces in the existing set but **not** in the target are deleted: `ip link delete {name}`
- Interfaces in the target but **not** existing are created: `ip link add link {parent} name {name} type vlan id {id}` and brought up

---

## Navigation

- [← API Reference Index](./index.md)
- [← Topology Endpoints](./topology.md)
- [← Node Endpoints](./nodes.md)
- [← WebSocket Terminal](./websocket.md)
- [Backend Developer Guide](../development.md)
