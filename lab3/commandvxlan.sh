#Use this script after using the commandnovxlan script for creating the network topology
# VXLAN Configuration Script using Open vSwitch
# This script configures VXLAN tunnels between:
# - C1 and C3 (VXLAN 100, subnet 10.0.1.0/24)
# - C2 and C4 (VXLAN 200, subnet 10.0.2.0/24)

#Clean up
sudo ovs-vsctl del-br ovs-vxlan100
sudo ovs-vsctl del-br ovs-vxlan200

# Create OVS bridges for VXLAN networks
sudo ovs-vsctl add-br ovs-vxlan100
sudo ovs-vsctl add-br ovs-vxlan200

# Add VXLAN port on ovs-vxlan100 for Router1 side
sudo ovs-vsctl add-port ovs-vxlan100 vxlan100 -- \
    set interface vxlan100 type=vxlan \
    options:remote_ip=172.20.0.3 \
    options:local_ip=172.20.0.2 \
    options:key=100 \
    options:dst_port=4789

# Add VXLAN port on ovs-vxlan200 for Router1 side
sudo ovs-vsctl add-port ovs-vxlan200 vxlan200 -- \
    set interface vxlan200 type=vxlan \
    options:remote_ip=172.20.0.3 \
    options:local_ip=172.20.0.2 \
    options:key=200 \
    options:dst_port=4789



# Remove old network configuration from C1
sudo docker exec C1 sh -c "ip addr flush dev eth0 2>/dev/null || true"

# Connect C1 to ovs-vxlan100
sudo ovs-docker add-port ovs-vxlan100 eth1 C1 --ipaddress=10.0.1.10/24

# Remove old network configuration from C2
sudo docker exec C2 sh -c "ip addr flush dev eth0 2>/dev/null || true"

# Connect C2 to ovs-vxlan200
sudo ovs-docker add-port ovs-vxlan200 eth1 C2 --ipaddress=10.0.2.10/24

# Remove old network configuration from C3
sudo docker exec C3 sh -c "ip addr flush dev eth0 2>/dev/null || true"

# Connect C3 to ovs-vxlan100
sudo ovs-docker add-port ovs-vxlan100 eth1 C3 --ipaddress=10.0.1.20/24

# Remove old network configuration from C4
sudo docker exec C4 sh -c "ip addr flush dev eth0 2>/dev/null || true"

# Connect C4 to ovs-vxlan200
sudo ovs-docker add-port ovs-vxlan200 eth1 C4 --ipaddress=10.0.2.20/24

# Create internal interfaces for gateways on ovs-vxlan100
sudo ovs-vsctl add-port ovs-vxlan100 vxlan100-gw -- set interface vxlan100-gw type=internal
sudo ip addr add 10.0.1.1/24 dev vxlan100-gw
sudo ip link set vxlan100-gw up

# Create internal interfaces for gateways on ovs-vxlan200
sudo ovs-vsctl add-port ovs-vxlan200 vxlan200-gw -- set interface vxlan200-gw type=internal
sudo ip addr add 10.0.2.1/24 dev vxlan200-gw
sudo ip link set vxlan200-gw up

# Set default gateway for C1
sudo ovs-docker add-port ovs-vxlan100 eth2 router1 --ipaddress=10.0.1.1/24

# Set default gateway for C2
sudo ovs-docker add-port ovs-vxlan200 eth3 router1 --ipaddress=10.0.2.1/24

# Set default gateway for C3
sudo ovs-docker add-port ovs-vxlan100 eth2 router2 --ipaddress=10.0.1.2/24

# Set default gateway for C4
sudo ovs-docker add-port ovs-vxlan200 eth3 router2 --ipaddress=10.0.2.2/24

echo "=== VXLAN Configuration Complete ==="
echo ""
echo "Network topology:"
echo "  VXLAN 100 (10.0.1.0/24): C1 (10.0.1.10) <--> C3 (10.0.1.20)"
echo "  VXLAN 200 (10.0.2.0/24): C2 (10.0.2.10) <--> C4 (10.0.2.20)"
echo ""

echo "=== Verifying OVS Configuration ==="
echo ""
echo "OVS Bridge ovs-vxlan100:"
sudo ovs-vsctl show | grep -A 10 "ovs-vxlan100"
echo ""
echo "OVS Bridge ovs-vxlan200:"
sudo ovs-vsctl show | grep -A 10 "ovs-vxlan200"
echo ""

echo "=== Testing VXLAN Connectivity ==="
sleep 2

echo "Testing C1 -> C3 (should work - same VXLAN 100):"
sudo docker exec C1 ping -c 3 10.0.1.20

echo ""
echo "Testing C2 -> C4 (should work - same VXLAN 200):"
sudo docker exec C2 ping -c 3 10.0.2.20

echo ""
echo "Testing C1 -> C4 (should fail - different VXLAN):"
sudo docker exec C1 ping -c 3 -W 2 10.0.2.20 2>&1 || echo "✓ Failed as expected - different VXLAN"

echo ""
echo "Testing C2 -> C3 (should fail - different VXLAN):"
sudo docker exec C2 ping -c 3 -W 2 10.0.1.20 2>&1 || echo "✓ Failed as expected - different VXLAN"

echo ""
echo "=== Verification Commands ==="
echo "Show all OVS bridges:"
echo "  sudo ovs-vsctl show"
echo ""
echo "Show VXLAN 100 configuration:"
echo "  sudo ovs-vsctl list interface vxlan100"
echo ""
echo "Show VXLAN 200 configuration:"
echo "  sudo ovs-vsctl list interface vxlan200"
echo ""
echo "Check C1 network interfaces:"
echo "  sudo docker exec C1 ip addr"
echo ""
echo "Check C3 network interfaces:"
echo "  sudo docker exec C3 ip addr"
