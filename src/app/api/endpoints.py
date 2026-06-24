from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.core.orchestrator import Orchestrator

router = APIRouter()

# --- Pydantic Models for Topology ---

class NodeSchema(BaseModel):
    name: str
    type: str  # 'router' | 'terminal'
    interfaces: List[str] = []

class LinkSchema(BaseModel):
    endpoints: List[str]

class TopologyDeployRequest(BaseModel):
    name: str = "sim-network"
    nodes: List[NodeSchema]
    links: List[LinkSchema]

# --- Pydantic Models for Router Config ---

class InterfaceConfig(BaseModel):
    name: str
    ip_address: Optional[str] = None
    vlan_mode: Optional[str] = None
    vlan_id: Optional[int] = None
    vlan_ids: Optional[List[int]] = None

class VlanInterfaceConfig(BaseModel):
    name: str
    parent: str
    vlan_id: int
    ip_address: Optional[str] = None

class OspfAreaConfig(BaseModel):
    area_id: str
    networks: List[str]

class OspfConfig(BaseModel):
    enabled: bool = False
    router_id: Optional[str] = None
    areas: List[OspfAreaConfig] = []

class RipConfig(BaseModel):
    enabled: bool = False
    networks: List[str] = []

class BgpNeighborConfig(BaseModel):
    ip_address: str
    remote_as: int

class BgpConfig(BaseModel):
    enabled: bool = False
    as_number: Optional[int] = None
    router_id: Optional[str] = None
    neighbors: List[BgpNeighborConfig] = []

class RoutingConfig(BaseModel):
    ospf: Optional[OspfConfig] = None
    rip: Optional[RipConfig] = None
    bgp: Optional[BgpConfig] = None

class StaticRouteConfig(BaseModel):
    destination: str
    next_hop: str

class RouterConfigureRequest(BaseModel):
    interfaces: List[InterfaceConfig] = []
    vlan_interfaces: List[VlanInterfaceConfig] = []
    routing: Optional[RoutingConfig] = None
    gateway: Optional[str] = None
    static_routes: List[StaticRouteConfig] = []

# --- Endpoints ---

@router.post("/topology/deploy")
async def deploy_topology(request: TopologyDeployRequest):
    orchestrator = Orchestrator()
    try:
        # Pydantic model to dict for internal usage
        data = request.model_dump()
        print(f"DEBUG DEPLOY TOPOLOGY PAYLOAD: {data}")
        result = orchestrator.deploy_topology(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deploy topology: {str(e)}")

@router.post("/topology/destroy")
async def destroy_topology():
    orchestrator = Orchestrator()
    try:
        result = orchestrator.destroy_topology()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to destroy topology: {str(e)}")

@router.get("/topology/status")
async def get_topology_status():
    orchestrator = Orchestrator()
    try:
        result = orchestrator.get_topology_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topology status: {str(e)}")

@router.post("/nodes/{node_name}/configure")
async def configure_node(node_name: str, request: RouterConfigureRequest):
    orchestrator = Orchestrator()
    try:
        data = request.model_dump()
        print(f"DEBUG CONFIGURE NODE {node_name} PAYLOAD: {data}")
        result = orchestrator.configure_node(node_name, data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure node {node_name}: {str(e)}")

@router.get("/nodes/{node_name}/runtime-info")
async def get_runtime_info(
    node_name: str,
    type: str = Query(..., description="Type of runtime info to retrieve: routing_table, arp_table, ospf_neighbors, bgp_neighbors, rip_status")
):
    valid_types = ["routing_table", "arp_table", "ospf_neighbors", "bgp_neighbors", "rip_status"]
    if type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type. Must be one of {', '.join(valid_types)}"
        )
        
    orchestrator = Orchestrator()
    try:
        result = orchestrator.get_runtime_info(node_name, type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get runtime info for {node_name}: {str(e)}")

@router.get("/topology/state")
async def get_topology_state(deployed: bool = Query(False, description="Whether to get the deployed state")):
    orchestrator = Orchestrator()
    try:
        result = orchestrator.get_topology_state(deployed=deployed)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topology state: {str(e)}")

@router.post("/topology/state")
async def save_topology_state(request: Dict[str, Any], deployed: bool = Query(False, description="Whether to save as deployed state")):
    orchestrator = Orchestrator()
    try:
        result = orchestrator.save_topology_state(request, deployed=deployed)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save topology state: {str(e)}")
