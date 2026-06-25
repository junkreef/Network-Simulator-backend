import unittest.mock as mock
from fastapi.testclient import TestClient

def test_read_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@mock.patch("app.api.endpoints.Orchestrator")
def test_deploy_topology_api(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.deploy_topology.return_value = {
        "status": "success",
        "message": "Topology deployed successfully"
    }

    payload = {
        "name": "sim-network",
        "nodes": [
            {"name": "r1", "type": "router", "interfaces": ["eth1", "eth2"]},
            {"name": "t1", "type": "terminal", "interfaces": ["eth1"]}
        ],
        "links": [
            {"endpoints": ["r1:eth1", "t1:eth1"]}
        ]
    }

    response = client.post("/api/v1/topology/deploy", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_orch.deploy_topology.assert_called_once_with(payload)

@mock.patch("app.api.endpoints.Orchestrator")
def test_destroy_topology_api(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.destroy_topology.return_value = {
        "status": "success",
        "message": "Topology destroyed successfully"
    }

    response = client.post("/api/v1/topology/destroy")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_orch.destroy_topology.assert_called_once()

@mock.patch("app.api.endpoints.Orchestrator")
def test_configure_node_api(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.configure_node.return_value = {
        "status": "success",
        "output": "Configuration applied successfully via frr-reload.py"
    }

    payload = {
        "interfaces": [
            {"name": "eth1", "ip_address": "10.0.0.1/24"}
        ],
        "vlan_interfaces": [
            {"name": "eth1.10", "parent": "eth1", "vlan_id": 10, "ip_address": "10.0.10.1/24"}
        ],
        "routing": {
            "ospf": {
                "enabled": True,
                "router_id": "1.1.1.1",
                "areas": [
                    {"area_id": "0", "networks": ["10.0.0.0/24"]}
                ]
            },
            "rip": None,
            "bgp": None
        }
    }

    response = client.post("/api/v1/nodes/r1/configure", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    expected_payload = {
        "interfaces": [
            {"name": "eth1", "ip_address": "10.0.0.1/24", "vlan_mode": None, "vlan_id": None, "vlan_ids": None}
        ],
        "vlan_interfaces": [
            {"name": "eth1.10", "parent": "eth1", "vlan_id": 10, "ip_address": "10.0.10.1/24"}
        ],
        "routing": {
            "ospf": {
                "enabled": True,
                "router_id": "1.1.1.1",
                "areas": [
                    {"area_id": "0", "networks": ["10.0.0.0/24"], "interfaces": [], "ranges": [], "area_type": "normal"}
                ],
                "redistribute": None,
                "default_information_originate": None
            },
            "rip": None,
            "bgp": None
        },
        "gateway": None,
        "static_routes": []
    }
    mock_orch.configure_node.assert_called_once_with("r1", expected_payload)

@mock.patch("app.api.endpoints.Orchestrator")
def test_get_runtime_info_api(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.get_runtime_info.return_value = {
        "node_name": "r1",
        "info_type": "routing_table",
        "raw_output": "Codes: K - kernel route..."
    }

    response = client.get("/api/v1/nodes/r1/runtime-info?type=routing_table")
    assert response.status_code == 200
    assert response.json()["info_type"] == "routing_table"
    mock_orch.get_runtime_info.assert_called_once_with("r1", "routing_table")

def test_get_runtime_info_invalid_type(client: TestClient):
    response = client.get("/api/v1/nodes/r1/runtime-info?type=invalid_type")
    assert response.status_code == 400


@mock.patch("app.api.endpoints.Orchestrator")
def test_configure_node_api_bgp_and_gateway(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.configure_node.return_value = {
        "status": "success",
        "output": "Configuration applied successfully"
    }

    payload = {
        "interfaces": [
            {"name": "eth1", "ip_address": "10.0.0.1/24"}
        ],
        "vlan_interfaces": [],
        "routing": {
            "bgp": {
                "enabled": True,
                "as_number": 65001,
                "router_id": "1.1.1.1",
                "neighbors": [
                    {"ip_address": "10.0.0.2", "remote_as": 65002}
                ]
            },
            "ospf": None,
            "rip": None
        },
        "gateway": "10.0.0.254"
    }

    response = client.post("/api/v1/nodes/r1/configure", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    expected_payload = {
        "interfaces": [
            {"name": "eth1", "ip_address": "10.0.0.1/24", "vlan_mode": None, "vlan_id": None, "vlan_ids": None}
        ],
        "vlan_interfaces": [],
        "routing": {
            "bgp": {
                "enabled": True,
                "as_number": 65001,
                "router_id": "1.1.1.1",
                "neighbors": [
                    {"ip_address": "10.0.0.2", "remote_as": 65002}
                ],
                "redistribute": None
            },
            "ospf": None,
            "rip": None
        },
        "gateway": "10.0.0.254",
        "static_routes": []
    }
    mock_orch.configure_node.assert_called_once_with("r1", expected_payload)

@mock.patch("app.api.endpoints.Orchestrator")
def test_get_topology_state_api(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.get_topology_state.return_value = {
        "nodes": [{"id": "node-1", "type": "router"}],
        "edges": []
    }
    
    response = client.get("/api/v1/topology/state?deployed=true")
    assert response.status_code == 200
    assert response.json()["nodes"][0]["id"] == "node-1"
    mock_orch.get_topology_state.assert_called_once_with(deployed=True)

@mock.patch("app.api.endpoints.Orchestrator")
def test_save_topology_state_api(mock_orch_class, client: TestClient):
    mock_orch = mock_orch_class.return_value
    mock_orch.save_topology_state.return_value = {
        "status": "success",
        "message": "Topology state saved successfully"
    }
    
    payload = {
        "nodes": [{"id": "node-1", "type": "router"}],
        "edges": []
    }
    
    response = client.post("/api/v1/topology/state?deployed=false", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_orch.save_topology_state.assert_called_once_with(payload, deployed=False)

