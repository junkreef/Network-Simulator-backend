"""REST API endpoints for network topology simulation.

Exposes endpoints for deploying/destroying topologies, managing node configuration
(IP addresses, VLANs, OSPF, RIP, BGP), and reading topology state and runtime status.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.orchestrator import Orchestrator

router = APIRouter()

# --- Pydantic Models for Topology ---

class NodeSchema(BaseModel):
    """Pydantic schema representing a network topology node (router or terminal)."""
    name: str
    type: str  # 'router' | 'terminal'
    interfaces: List[str] = []

class LinkSchema(BaseModel):
    """Pydantic schema representing a link connection between two nodes."""
    endpoints: List[str]

class TopologyDeployRequest(BaseModel):
    """Pydantic schema for topology deployment requests."""
    name: str = "sim-network"
    nodes: List[NodeSchema]
    links: List[LinkSchema]

# --- Pydantic Models for Router Config ---

class InterfaceConfig(BaseModel):
    """Pydantic schema representing interface configuration, including IP, VLAN mode, and VLAN IDs."""
    name: str
    ip_address: Optional[str] = None
    vlan_mode: Optional[str] = None
    vlan_id: Optional[int] = None
    vlan_ids: Optional[List[int]] = None

class VlanInterfaceConfig(BaseModel):
    """Pydantic schema representing VLAN subinterface configuration."""
    name: str
    parent: str
    vlan_id: int
    ip_address: Optional[str] = None

class OspfAreaConfig(BaseModel):
    """Pydantic schema representing an OSPF area and its networks."""
    area_id: str
    networks: List[str]

class OspfConfig(BaseModel):
    """Pydantic schema representing OSPF routing configuration."""
    enabled: bool = False
    router_id: Optional[str] = None
    areas: List[OspfAreaConfig] = []

class RipConfig(BaseModel):
    """Pydantic schema representing RIP routing configuration."""
    enabled: bool = False
    networks: List[str] = []

class BgpNeighborConfig(BaseModel):
    """Pydantic schema representing a BGP neighbor config."""
    ip_address: str
    remote_as: int

class BgpConfig(BaseModel):
    """Pydantic schema representing BGP routing configuration."""
    enabled: bool = False
    as_number: Optional[int] = None
    router_id: Optional[str] = None
    neighbors: List[BgpNeighborConfig] = []

class RoutingConfig(BaseModel):
    """Pydantic schema grouping OSPF, RIP, and BGP routing configurations."""
    ospf: Optional[OspfConfig] = None
    rip: Optional[RipConfig] = None
    bgp: Optional[BgpConfig] = None

class StaticRouteConfig(BaseModel):
    """Pydantic schema representing static route destination and next-hop configuration."""
    destination: str
    next_hop: str

class RouterConfigureRequest(BaseModel):
    """Pydantic schema for configuring router interfaces, static routing, and dynamic routing protocols."""
    interfaces: List[InterfaceConfig] = []
    vlan_interfaces: List[VlanInterfaceConfig] = []
    routing: Optional[RoutingConfig] = None
    gateway: Optional[str] = None
    static_routes: List[StaticRouteConfig] = []

# --- Endpoints ---

@router.post("/topology/deploy")
async def deploy_topology(request: TopologyDeployRequest):
    """Deploys a containerlab network topology based on the provided nodes and links.

    Renders the topology YAML, spawns the Docker containers, and sets up interfaces.
    """
    orchestrator = Orchestrator()
    try:
        # Pydantic model to dict for internal usage
        data = request.model_dump()
        print(f"DEBUG DEPLOY TOPOLOGY PAYLOAD: {data}")
        result = orchestrator.deploy_topology(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deploy topology: {str(e)}") from e

@router.post("/topology/destroy")
async def destroy_topology():
    """Destroys the currently active containerlab topology, cleaning up docker containers."""
    orchestrator = Orchestrator()
    try:
        result = orchestrator.destroy_topology()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to destroy topology: {str(e)}") from e

@router.get("/topology/status")
async def get_topology_status():
    """Retrieves the runtime status (running or not) of the deployed nodes in the topology."""
    orchestrator = Orchestrator()
    try:
        result = orchestrator.get_topology_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topology status: {str(e)}") from e

@router.post("/nodes/{node_name}/configure")
async def configure_node(node_name: str, request: RouterConfigureRequest):
    """Configures interfaces, routing, and dynamic routing protocols (OSPF/RIP/BGP) on a specific node.

    Generates the new configuration (e.g., frr.conf) and applies it dynamically.
    """
    orchestrator = Orchestrator()
    try:
        data = request.model_dump()
        print(f"DEBUG CONFIGURE NODE {node_name} PAYLOAD: {data}")
        result = orchestrator.configure_node(node_name, data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure node {node_name}: {str(e)}") from e

@router.get("/nodes/{node_name}/runtime-info")
async def get_runtime_info(
    node_name: str,
    info_type: str = Query(..., alias="type", description="Type of runtime info to retrieve: routing_table, arp_table, ospf_neighbors, bgp_neighbors, rip_status")
):
    """Retrieves runtime details (routing table, ARP table, OSPF/BGP/RIP status) from inside a node's container."""
    valid_types = ["routing_table", "arp_table", "ospf_neighbors", "bgp_neighbors", "rip_status"]
    if info_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type. Must be one of {', '.join(valid_types)}"
        )

    orchestrator = Orchestrator()
    try:
        result = orchestrator.get_runtime_info(node_name, info_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get runtime info for {node_name}: {str(e)}") from e

@router.get("/topology/state")
async def get_topology_state(deployed: bool = Query(False, description="Whether to get the deployed state")):
    """Retrieves the saved frontend UI topology state (nodes and edges layout)."""
    orchestrator = Orchestrator()
    try:
        result = orchestrator.get_topology_state(deployed=deployed)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topology state: {str(e)}") from e

@router.post("/topology/state")
async def save_topology_state(request: Dict[str, Any], deployed: bool = Query(False, description="Whether to save as deployed state")):
    """Saves the frontend UI topology state (nodes and edges layout) to a persistent file."""
    orchestrator = Orchestrator()
    try:
        result = orchestrator.save_topology_state(request, deployed=deployed)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save topology state: {str(e)}") from e
