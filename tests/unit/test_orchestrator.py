import os
import unittest.mock as mock
import pytest
from app.core.orchestrator import Orchestrator
from app.core.config import settings

def test_deploy_topology_rendering(tmp_path, monkeypatch):
    # Set settings.CONFIG_DIR to tmp_path to avoid writing to actual configs during test
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    
    orch = Orchestrator()
    
    # Mock shell commands
    mock_run_cmd = mock.MagicMock()
    monkeypatch.setattr(orch, "_run_cmd", mock_run_cmd)
    
    topology_data = {
        "name": "test-net",
        "nodes": [
            {"name": "r1", "type": "router", "interfaces": ["eth1", "eth2"]},
            {"name": "t1", "type": "terminal", "interfaces": ["eth1"]}
        ],
        "links": [
            {"endpoints": ["r1:eth1", "t1:eth1"]}
        ]
    }
    
    res = orch.deploy_topology(topology_data)
    
    assert res["status"] == "success"
    
    # Check if directories were created
    assert os.path.exists(os.path.join(settings.CONFIG_DIR, "r1"))
    assert os.path.exists(os.path.join(settings.CONFIG_DIR, "r1", "daemons"))
    assert os.path.exists(os.path.join(settings.CONFIG_DIR, "r1", "vtysh.conf"))
    assert os.path.exists(os.path.join(settings.CONFIG_DIR, "r1", "frr.conf"))
    
    # Verify written topology file content
    topo_path = os.path.join(settings.CONFIG_DIR, "topology.clab.yml")
    assert os.path.exists(topo_path)
    with open(topo_path, "r") as f:
        topo_content = f.read()
        
    assert "name: test-net" in topo_content
    assert "r1:" in topo_content
    assert "image: alpine-frr:latest" in topo_content
    assert "t1:" in topo_content
    assert "image: alpine-terminal:latest" in topo_content
    assert "- \"r1:eth1\"" in topo_content
    assert "- \"t1:eth1\"" in topo_content
    
    # Verify containerlab deploy was executed
    mock_run_cmd.assert_called_once_with(["containerlab", "deploy", "-t", topo_path, "--reconfigure"])

@mock.patch("app.core.orchestrator.Orchestrator._get_container_by_name")
def test_configure_node_rendering(mock_get_container, tmp_path, monkeypatch):
    # Set settings.CONFIG_DIR to tmp_path
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    
    mock_container = mock.MagicMock()
    mock_get_container.return_value = mock_container
    # Return exit_code=0 for container commands
    mock_container.exec_run.return_value = mock.MagicMock(exit_code=0, output=b"")
    mock_container.image.tags = ["alpine-frr:latest"]
    
    orch = Orchestrator()
    
    config_data = {
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
            }
        }
    }
    
    res = orch.configure_node("r1", config_data)
    assert res["status"] == "success"
    
    # Check if configurations were written to CONFIG_DIR/r1/frr.conf
    frr_conf_path = os.path.join(settings.CONFIG_DIR, "r1", "frr.conf")
    assert os.path.exists(frr_conf_path)
    with open(frr_conf_path, "r") as f:
        written_content = f.read()
        
    assert "interface eth1" in written_content
    assert "ip address 10.0.0.1/24" in written_content
    assert "interface eth1.10" in written_content
    assert "ip address 10.0.10.1/24" in written_content
    assert "router ospf" in written_content
    assert "ospf router-id 1.1.1.1" in written_content
    assert "network 10.0.0.0/24 area 0" in written_content
