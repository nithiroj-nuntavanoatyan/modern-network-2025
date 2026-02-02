#!/bin/bash

# 1. Cleanup existing environment
echo "Cleaning up..."
sudo docker stop host1 host2 host3 host4 2>/dev/null
sudo docker rm host1 host2 host3 host4 2>/dev/null
sudo ovn-nbctl ls-del ls-test 2>/dev/null
sudo ovs-vsctl del-br br-int 2>/dev/null
for i in {1..4}; do
    sudo ip link delete veth$i 2>/dev/null
done

# 2. Initialization
sudo apt update && sudo apt install -y openvswitch-switch ovn-host ovn-central docker.io
sudo systemctl enable --now openvswitch-switch ovn-central 

# Set OVN DB connections
sudo ovn-nbctl set-connection ptcp:6641:0.0.0.0
sudo ovn-sbctl set-connection ptcp:6642:0.0.0.0

# 3. OVN Logical Networking
# Create logical Switch and Ports
sudo ovn-nbctl ls-add ls-test
for i in {1..4}; do
    sudo ovn-nbctl lsp-add ls-test lp-host$i
    sudo ovn-nbctl lsp-set-addresses lp-host$i "02:00:00:00:00:0$i 10.0.0.$i/24"
done

# 4. Configure OVS & OVN Controller
sudo ovs-vsctl set open . external-ids:system-id=ovs-host
sudo ovs-vsctl set open . external-ids:ovn-remote=tcp:127.0.0.1:6642
sudo ovs-vsctl set open . external-ids:ovn-encap-type=geneve
sudo ovs-vsctl set open . external-ids:ovn-encap-ip=127.0.0.1

# 5. Create Veth Pairs and Attach to Integration Bridge (br-int)
# Note: OVN controller automatically creates br-int
for i in {1..4}; do
    sudo ip link add veth$i type veth peer name veth$i-c
    sudo ip link set veth$i up
    # Attach all ports to the integration bridge
    sudo ovs-vsctl add-port br-int veth$i -- set Interface veth$i external-ids:iface-id=lp-host$i
done

# 6. Container Setup
for i in {1..4}; do
    sudo docker run -dit --name host$i --net=none --privileged alpine sh
    PID=$(sudo docker inspect -f '{{.State.Pid}}' host$i)
    sudo ip link set veth$i-c netns $PID
    
    sudo nsenter -t $PID -n ip link set veth$i-c name eth0
    sudo nsenter -t $PID -n ip addr add 10.0.0.$i/24 dev eth0
    sudo nsenter -t $PID -n ip link set eth0 address 02:00:00:00:00:0$i
    sudo nsenter -t $PID -n ip link set eth0 up
done

# 7. Verification
echo "Testing connectivity host1 -> host4..."
for i in {1..4}; do
    sudo docker exec host1 ping -c 3 10.0.0.$i
done