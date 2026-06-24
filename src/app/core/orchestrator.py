import os
import shutil
import subprocess
import json
import logging
import docker
import time
from jinja2 import Environment, FileSystemLoader
from app.core.config import settings

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not connect to Docker daemon: {e}")
            self.docker_client = None
            
        self.jinja_env = Environment(
            loader=FileSystemLoader(settings.TEMPLATE_DIR),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def _run_cmd(self, cmd: list) -> subprocess.CompletedProcess:
        """Run a shell command and return the result."""
        logger.info(f"Running command: {' '.join(cmd)}")
        # Check if running under test or docker where sudo might not be needed,
        # but containerlab typically needs sudo. We will prepend sudo if containerlab is called.
        if cmd[0] == "containerlab" and os.getuid() != 0:
            cmd = ["sudo"] + cmd
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with exit code {e.returncode}. Stderr: {e.stderr}")
            raise e

    def get_topology_filepath(self) -> str:
        return os.path.join(settings.CONFIG_DIR, "topology.clab.yml")

    def deploy_topology(self, topology_data: dict) -> dict:
        """
        Deploy the containerlab topology.
        topology_data contains: name, nodes, links
        """
        topology_name = topology_data.get("name", "sim-network")
        nodes = topology_data.get("nodes", [])
        links = topology_data.get("links", [])

        # 1. Setup config directories for routers
        for node in nodes:
            node_name = node.get("name")
            node_type = node.get("type")
            if node_type == "router":
                node_config_dir = os.path.join(settings.CONFIG_DIR, topology_name, node_name)
                os.makedirs(node_config_dir, exist_ok=True)
                try:
                    os.chmod(node_config_dir, 0o777)
                except Exception:
                    pass
                
                # Write daemons file
                daemons_path = os.path.join(node_config_dir, "daemons")
                if os.path.isdir(daemons_path):
                    shutil.rmtree(daemons_path)
                with open(daemons_path, "w") as f:
                    f.write(
                        "zebra=yes\n"
                        "bgpd=yes\n"
                        "ospfd=yes\n"
                        "ripd=yes\n"
                        "ospf6d=no\n"
                        "ripngd=no\n"
                        "isisd=no\n"
                        "pimd=no\n"
                        "ldpd=no\n"
                        "nhrpd=no\n"
                        "eigrpd=no\n"
                        "babeld=no\n"
                        "sharpd=no\n"
                        "pbrd=no\n"
                        "bfdd=no\n"
                        "fabricd=no\n"
                        "vrrpd=no\n"
                        "pathd=no\n"
                    )
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    os.chmod(daemons_path, 0o777)
                except Exception:
                    pass
                
                # Write vtysh.conf
                vtysh_conf_path = os.path.join(node_config_dir, "vtysh.conf")
                if os.path.isdir(vtysh_conf_path):
                    shutil.rmtree(vtysh_conf_path)
                with open(vtysh_conf_path, "w") as f:
                    f.write("service integrated-vtysh-config\n")
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    os.chmod(vtysh_conf_path, 0o777)
                except Exception:
                    pass
 
                # Write initial empty frr.conf if not exists
                frr_conf_path = os.path.join(node_config_dir, "frr.conf")
                if os.path.exists(frr_conf_path) and os.path.isdir(frr_conf_path):
                    shutil.rmtree(frr_conf_path)
                with open(frr_conf_path, "w") as f:
                    f.write("log file /var/log/frr/frr.log\n!\n")
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    os.chmod(frr_conf_path, 0o777)
                except Exception:
                    pass

        # 2. Render topology.clab.yml
        template = self.jinja_env.get_template("topology.clab.yml.j2")
        rendered_yml = template.render(
            topology_name=topology_name,
            nodes=nodes,
            links=links,
            config_dir=settings.CONFIG_DIR
        )

        topo_filepath = self.get_topology_filepath()
        with open(topo_filepath, "w") as f:
            f.write(rendered_yml)
            f.flush()
            os.fsync(f.fileno())

        # 3. Execute containerlab deploy
        # We use --reconfigure to ensure everything is rebuilt cleanly
        import time
        time.sleep(1)
        cmd = ["containerlab", "deploy", "-t", topo_filepath, "--reconfigure"]
        self._run_cmd(cmd)

        return {
            "status": "success",
            "message": "Topology deployed successfully",
            "details": {
                "name": topology_name,
                "container_count": len(nodes)
            }
        }

    def destroy_topology(self) -> dict:
        """Destroy the containerlab topology."""
        topo_filepath = self.get_topology_filepath()
        if not os.path.exists(topo_filepath):
            return {
                "status": "success",
                "message": "No topology configuration found to destroy"
            }

        cmd = ["containerlab", "destroy", "-t", topo_filepath, "--cleanup"]
        self._run_cmd(cmd)

        # Cleanup config directories
        try:
            for item in os.listdir(settings.CONFIG_DIR):
                item_path = os.path.join(settings.CONFIG_DIR, item)
                if os.path.isdir(item_path) and item != ".venv":
                    shutil.rmtree(item_path)
            # Remove the topology file as well
            if os.path.exists(topo_filepath):
                os.remove(topo_filepath)
        except Exception as e:
            logger.warning(f"Error during configs cleanup: {e}")

        return {
            "status": "success",
            "message": "Topology destroyed successfully"
        }

    def get_topology_status(self) -> dict:
        """Get the topology status using containerlab inspect."""
        topo_filepath = self.get_topology_filepath()
        if not os.path.exists(topo_filepath):
            logger.warning(f"Topology file does not exist at {topo_filepath}")
            return {
                "topology_name": "",
                "status": "stopped",
                "nodes": []
            }

        # Parse the expected topology name from the configuration file
        expected_name = ""
        try:
            with open(topo_filepath, "r") as f:
                for line in f:
                    if line.strip().startswith("name:"):
                        expected_name = line.split(":", 1)[1].strip()
                        break
        except Exception as e:
            logger.warning(f"Failed to read name from topology file: {e}")

        try:
            # Run containerlab inspect to get JSON format status
            cmd = ["containerlab", "inspect", "-t", topo_filepath, "--format", "json"]
            
            # Retry loop to account for containerlab/docker startup state sync delays
            data = {}
            for attempt in range(5):
                try:
                    result = self._run_cmd(cmd)
                    stdout = result.stdout
                    # Safe JSON parsing
                    start_idx = stdout.find('{')
                    if start_idx == -1:
                        start_idx = stdout.find('[')
                    if start_idx != -1:
                        parsed_data = json.loads(stdout[start_idx:])
                    else:
                        parsed_data = json.loads(stdout)
                    
                    if parsed_data and (not expected_name or expected_name in parsed_data):
                        data = parsed_data
                        break
                except Exception as e:
                    if attempt == 4:
                        raise e
                logger.warning(f"containerlab inspect not ready yet, retrying in 2s... (attempt {attempt+1}/5)")
                time.sleep(2)
            
            topology_name = ""
            nodes_list = []
            if data:
                if expected_name and expected_name in data:
                    topology_name = expected_name
                    nodes_list = data[expected_name]
                else:
                    topology_name = list(data.keys())[0]
                    nodes_list = data[topology_name]
            
            nodes_status = []
            for node in nodes_list:
                nodes_status.append({
                    "name": node.get("name"),
                    "kind": node.get("kind"),
                    "state": node.get("state"),
                    "ipv4_address": node.get("ipv4_address")
                })
            
            return {
                "topology_name": topology_name,
                "status": "running" if nodes_status else "stopped",
                "nodes": nodes_status
            }
        except Exception as e:
            logger.error(f"Error getting topology status: {e}")
            return {
                "topology_name": "",
                "status": "error",
                "message": str(e),
                "nodes": []
            }

    def configure_node(self, node_name: str, config_data: dict) -> dict:
        """
        Configure an FRR router node, L2 switch node, or a standard terminal node.
        config_data contains: interfaces, vlan_interfaces, routing
        """
        if not self.docker_client:
            raise Exception("Docker client not initialized")

        container = self._get_container_by_name(node_name)
        if not container:
            raise Exception(f"Container for node {node_name} not found")

        # Determine if it's a router or switch
        image_name = container.image.tags[0] if container.image.tags else ""
        is_router = "frr" in image_name or "router" in node_name
        is_switch = "switch" in image_name or "switch" in node_name

        if is_switch:
            # Create br0 with vlan_filtering=1, forward_delay=0, stp=0 and bring it up
            container.exec_run(["ip", "link", "add", "name", "br0", "type", "bridge", "vlan_filtering", "1", "forward_delay", "0", "stp_state", "0"])
            container.exec_run(["ip", "link", "set", "dev", "br0", "up"])

            interfaces = config_data.get("interfaces", [])
            for iface in interfaces:
                if_name = iface.get("name")
                if not if_name:
                    continue

                # Add physical interface to bridge and bring it up
                container.exec_run(["ip", "link", "set", "dev", if_name, "master", "br0"])
                container.exec_run(["ip", "link", "set", "dev", if_name, "up"])

                # Remove default vlan 1
                container.exec_run(["bridge", "vlan", "del", "dev", if_name, "vid", "1"])

                vlan_mode_raw = iface.get("vlan_mode")
                vlan_mode = vlan_mode_raw.lower() if vlan_mode_raw else "access"
                if vlan_mode == "access":
                    vlan_id = iface.get("vlan_id")
                    if vlan_id is not None:
                        res = container.exec_run(["bridge", "vlan", "add", "dev", if_name, "vid", str(vlan_id), "pvid", "untagged"])
                        if res.exit_code != 0:
                            logger.error(f"Failed to configure access vlan {vlan_id} on {if_name}: {res.output.decode()}")
                elif vlan_mode == "trunk":
                    vlan_ids = iface.get("vlan_ids", [])
                    for vid in vlan_ids:
                        res = container.exec_run(["bridge", "vlan", "add", "dev", if_name, "vid", str(vid)])
                        if res.exit_code != 0:
                            logger.error(f"Failed to configure trunk vlan {vid} on {if_name}: {res.output.decode()}")

            return {
                "status": "success",
                "output": "L2 Switch configured successfully with VLAN filtering"
            }

        # 1. Manage VLAN subinterfaces on Linux kernel inside the container
        vlan_interfaces = config_data.get("vlan_interfaces", [])
        self._sync_vlan_interfaces(container, vlan_interfaces)

        # Apply IP addresses on VLAN interfaces for both router (kernel side) and terminal
        for viface in vlan_interfaces:
            v_name = viface.get("name")
            v_ip = viface.get("ip_address")
            if v_name and v_ip:
                # Add IP address directly to Linux kernel (needed for terminal, FRR routers will sync via frr.conf but doing it directly doesn't hurt)
                container.exec_run(["ip", "addr", "flush", "dev", v_name])
                res = container.exec_run(["ip", "addr", "add", v_ip, "dev", v_name])
                if res.exit_code != 0:
                    logger.warning(f"Direct IP assignment failed for {v_name}: {res.output.decode()}")

        if not is_router:
            # For terminal/non-router nodes, directly configure physical interfaces
            interfaces = config_data.get("interfaces", [])
            for iface in interfaces:
                if_name = iface.get("name")
                if_ip = iface.get("ip_address")
                if if_name and if_ip:
                    container.exec_run(["ip", "addr", "flush", "dev", if_name])
                    res = container.exec_run(["ip", "addr", "add", if_ip, "dev", if_name])
                    if res.exit_code != 0:
                        logger.error(f"Failed to assign IP to {if_name}: {res.output.decode()}")
                    container.exec_run(["ip", "link", "set", "dev", if_name, "up"])
            
            # Configure default gateway if specified
            gateway = config_data.get("gateway")
            if gateway:
                container.exec_run(["ip", "route", "del", "default"])
                res = container.exec_run(["ip", "route", "add", "default", "via", gateway])
                if res.exit_code != 0:
                    logger.error(f"Failed to configure default gateway {gateway}: {res.output.decode()}")

            return {
                "status": "success",
                "output": "Terminal interfaces and routing configured successfully"
            }

        # Convert gateway to default static route if router
        static_routes = config_data.get("static_routes", [])
        gateway = config_data.get("gateway")
        if gateway:
            # Handle possible Pydantic model conversion inside list
            static_routes = [
                dict(r) if not isinstance(r, dict) else r for r in static_routes
            ]
            if not any(r.get("destination") == "0.0.0.0/0" or r.get("destination") == "0.0.0.0" for r in static_routes):
                static_routes = list(static_routes)
                static_routes.append({"destination": "0.0.0.0/0", "next_hop": gateway})

        # 2. Render frr.conf for router
        template = self.jinja_env.get_template("frr.conf.j2")
        rendered_conf = template.render(
            interfaces=config_data.get("interfaces", []),
            vlan_interfaces=vlan_interfaces,
            routing=config_data.get("routing", {}),
            static_routes=static_routes
        )

        # Wait for vtysh/daemons to be ready (up to 15 seconds)
        for i in range(15):
            res = container.exec_run(["vtysh", "-c", "write"])
            if res.exit_code == 0:
                break
            logger.info(f"Waiting for vtysh to be responsive inside {node_name}... ({i+1}/15)")
            time.sleep(1)

        # 3. Apply config using frr-reload.py
        # Write to temporary file in container /etc/frr/frr.conf.new
        write_cmd = f"cat << 'EOF' > /etc/frr/frr.conf.new\n{rendered_conf}\nEOF"
        exec_res = container.exec_run(["sh", "-c", write_cmd])
        if exec_res.exit_code != 0:
            raise Exception(f"Failed to write frr.conf.new in container: {exec_res.output.decode()}")

        # Run frr-reload.py --reload /etc/frr/frr.conf.new
        reload_cmd = ["/usr/lib/frr/frr-reload.py", "--reload", "/etc/frr/frr.conf.new"]
        reload_res = container.exec_run(reload_cmd)
        
        # Cleanup temp file
        container.exec_run(["rm", "-f", "/etc/frr/frr.conf.new"])

        if reload_res.exit_code != 0:
            error_output = reload_res.output.decode()
            logger.error(f"frr-reload.py failed: {error_output}")
            raise Exception(f"Configuration reload failed: {error_output}")

        # If success, update host config file for persistent configuration (mounted as rw)
        topo_name = "sim-network"
        topo_filepath = self.get_topology_filepath()
        if os.path.exists(topo_filepath):
            try:
                with open(topo_filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("name:"):
                            topo_name = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass
        node_config_path = os.path.join(settings.CONFIG_DIR, topo_name, node_name, "frr.conf")
        os.makedirs(os.path.dirname(node_config_path), exist_ok=True)
        with open(node_config_path, "w", encoding="utf-8") as f:
            f.write(rendered_conf)
        try:
            os.chmod(node_config_path, 0o777)
        except Exception:
            pass

        return {
            "status": "success",
            "output": reload_res.output.decode() or "Configuration applied successfully via frr-reload.py"
        }


    def get_runtime_info(self, node_name: str, info_type: str) -> dict:
        """Get runtime routing / ARP / neighbor information for a node."""
        if not self.docker_client:
            raise Exception("Docker client not initialized")

        container = self._get_container_by_name(node_name)
        if not container:
            raise Exception(f"Container for node {node_name} not found")

        # Determine node type (router vs terminal) by checking image or command output
        # Let's inspect container image name
        image_name = container.image.tags[0] if container.image.tags else ""
        is_router = "frr" in image_name or "router" in node_name

        cmd = []
        if info_type == "routing_table":
            if is_router:
                cmd = ["vtysh", "-c", "show ip route"]
            else:
                cmd = ["ip", "route", "show"]
        elif info_type == "arp_table":
            cmd = ["ip", "neighbor", "show"]
        elif info_type == "ospf_neighbors":
            if is_router:
                cmd = ["vtysh", "-c", "show ip ospf neighbor"]
            else:
                raise Exception("OSPF neighbors only available on routers")
        elif info_type == "bgp_neighbors":
            if is_router:
                cmd = ["vtysh", "-c", "show ip bgp summary"]
            else:
                raise Exception("BGP neighbors only available on routers")
        elif info_type == "rip_status":
            if is_router:
                cmd = ["vtysh", "-c", "show ip rip"]
            else:
                raise Exception("RIP status only available on routers")
        else:
            raise Exception(f"Unknown info type: {info_type}")

        exec_res = container.exec_run(cmd)
        if exec_res.exit_code != 0:
            raise Exception(f"Failed to execute command {' '.join(cmd)}: {exec_res.output.decode()}")

        return {
            "node_name": node_name,
            "info_type": info_type,
            "raw_output": exec_res.output.decode()
        }

    def _get_container_by_name(self, node_name: str):
        """Find a docker container by its short name (e.g. 'r1') or containerlab full name (e.g. 'clab-sim-network-r1')."""
        topo_name = ""
        topo_filepath = self.get_topology_filepath()
        if os.path.exists(topo_filepath):
            try:
                with open(topo_filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("name:"):
                            topo_name = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass

        containers = self.docker_client.containers.list()
        for c in containers:
            if c.name == node_name:
                return c
            if topo_name and c.name == f"clab-{topo_name}-{node_name}":
                return c
            if not topo_name and c.name.endswith(f"-{node_name}"):
                return c
        return None

    def _sync_vlan_interfaces(self, container, target_vlans: list):
        """
        Sync VLAN subinterfaces inside the container.
        target_vlans: list of dict with keys: name, parent, vlan_id, ip_address
        """
        # Get existing interfaces
        exec_res = container.exec_run(["ip", "link", "show"])
        if exec_res.exit_code != 0:
            logger.warning("Could not read ip link in container")
            return
            
        ip_link_output = exec_res.output.decode()
        
        # Simple parser for vlan interfaces (which typically have @parent or are named parent.id)
        # Or we can check if they contain '.' (e.g. eth1.10)
        existing_vlans = []
        for line in ip_link_output.split("\n"):
            if ": " in line:
                parts = line.split(": ")
                if len(parts) >= 2:
                    iface_name = parts[1].split("@")[0].strip()
                    if "." in iface_name:
                        existing_vlans.append(iface_name)

        target_names = [v.get("name") for v in target_vlans if v.get("name")]

        # 1. Delete removed VLAN interfaces
        for ev in existing_vlans:
            if ev not in target_names:
                del_cmd = ["ip", "link", "delete", ev]
                container.exec_run(del_cmd)

        # 2. Add or update VLAN interfaces
        for tv in target_vlans:
            v_name = tv.get("name")
            v_parent = tv.get("parent")
            v_id = tv.get("vlan_id")
            
            if not v_name or not v_parent or v_id is None:
                continue

            if v_name not in existing_vlans:
                # Add VLAN interface
                add_cmd = ["ip", "link", "add", "link", v_parent, "name", v_name, "type", "vlan", "id", str(v_id)]
                res = container.exec_run(add_cmd)
                if res.exit_code != 0:
                    logger.error(f"Failed to create VLAN interface {v_name}: {res.output.decode()}")
                    continue
                    
                up_cmd = ["ip", "link", "set", "dev", v_name, "up"]
                container.exec_run(up_cmd)

    def save_topology_state(self, state_data: dict, deployed: bool = False) -> dict:
        """Save the topology UI state (nodes, edges) to a JSON file."""
        filename = "topology_deployed_state.json" if deployed else "topology_state.json"
        filepath = os.path.join(settings.CONFIG_DIR, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            return {
                "status": "success",
                "message": f"Topology state {'deployed' if deployed else 'saved'} successfully"
            }
        except Exception as e:
            logger.error("Failed to save topology state (deployed=%s): %s", deployed, e)
            raise e

    def get_topology_state(self, deployed: bool = False) -> dict:
        """Get the topology UI state (nodes, edges) from a JSON file."""
        filename = "topology_deployed_state.json" if deployed else "topology_state.json"
        filepath = os.path.join(settings.CONFIG_DIR, filename)
        if not os.path.exists(filepath):
            return {"nodes": [], "edges": []}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to read topology state (deployed=%s): %s", deployed, e)
            return {"nodes": [], "edges": []}
