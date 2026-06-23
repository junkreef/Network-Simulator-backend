import time
import pytest
import docker
from fastapi.testclient import TestClient

def test_full_integration_flow(client: TestClient):
    # Ensure any previous topology is destroyed before starting
    client.post("/api/v1/topology/destroy")

    # 1. Deploy topology
    deploy_payload = {
        "name": "sim-network",
        "nodes": [
            {"name": "r1", "type": "router", "interfaces": ["eth1"]},
            {"name": "t1", "type": "terminal", "interfaces": ["eth1"]}
        ],
        "links": [
            {"endpoints": ["r1:eth1", "t1:eth1"]}
        ]
    }
    
    deploy_res = client.post("/api/v1/topology/deploy", json=deploy_payload)
    assert deploy_res.status_code == 200
    assert deploy_res.json()["status"] == "success"

    # Wait a bit for containerlab startup to settle (especially FRR daemons)
    time.sleep(10)

    try:
        # 2. Check topology status
        status_res = client.get("/api/v1/topology/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["topology_name"] == "sim-network"
        assert status_data["status"] == "running"
        
        nodes = {n["name"]: n for n in status_data["nodes"]}
        # Names will be clab-sim-network-r1 and clab-sim-network-t1
        assert "clab-sim-network-r1" in nodes
        assert "clab-sim-network-t1" in nodes
        
        # 3. Configure r1
        r1_config = {
            "interfaces": [
                {"name": "eth1", "ip_address": "10.0.0.1/24"}
            ],
            "vlan_interfaces": [],
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
        r1_conf_res = client.post("/api/v1/nodes/r1/configure", json=r1_config)
        assert r1_conf_res.status_code == 200
        assert r1_conf_res.json()["status"] == "success"

        # 4. Configure t1
        t1_config = {
            "interfaces": [
                {"name": "eth1", "ip_address": "10.0.0.2/24"}
            ],
            "vlan_interfaces": [],
            "routing": {}
        }
        t1_conf_res = client.post("/api/v1/nodes/t1/configure", json=t1_config)
        assert t1_conf_res.status_code == 200
        assert t1_conf_res.json()["status"] == "success"

        # Give some time for IPs to be applied and interfaces to wake up
        time.sleep(2)

        # 5. Check data plane connectivity (Ping from t1 to r1)
        docker_client = docker.from_env()
        # Find container
        t1_container = None
        for c in docker_client.containers.list():
            if c.name == "clab-sim-network-t1":
                t1_container = c
                break
                
        assert t1_container is not None, "t1 container not found via docker-py"
        
        # Run ping command inside t1 to r1's IP (10.0.0.1)
        ping_res = t1_container.exec_run(["ping", "-c", "3", "10.0.0.1"])
        print(f"Ping Output: {ping_res.output.decode()}")
        assert ping_res.exit_code == 0, f"Ping failed: {ping_res.output.decode()}"

        # 6. Verify runtime info endpoints
        info_res = client.get("/api/v1/nodes/r1/runtime-info?type=routing_table")
        assert info_res.status_code == 200
        assert "10.0.0.0/24" in info_res.json()["raw_output"]

        info_res = client.get("/api/v1/nodes/r1/runtime-info?type=arp_table")
        assert info_res.status_code == 200
        # arp table should contain 10.0.0.2
        assert "10.0.0.2" in info_res.json()["raw_output"]

    finally:
        # 7. Destroy topology
        destroy_res = client.post("/api/v1/topology/destroy")
        assert destroy_res.status_code == 200
        assert destroy_res.json()["status"] == "success"
