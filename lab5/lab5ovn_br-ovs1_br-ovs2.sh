#!/bin/bash

# --- 1. Cleanup ---
echo "Cleaning up..."
sudo docker stop host1 host2 host3 host4 2>/dev/null
sudo docker rm host1 host2 host3 host4 2>/dev/null
sudo ovn-nbctl ls-del ls-test 2>/dev/null
sudo ovs-vsctl del-br br-ovs1 2>/dev/null
sudo ovs-vsctl del-br br-ovs2 2>/dev/null
sudo ovs-vsctl del-br br-int 2>/dev/null
for i in {1..4}; do
    sudo ip link delete veth$i 2>/dev/null
done

# --- 2. Initialization ---
sudo apt update && sudo apt install -y openvswitch-switch ovn-host ovn-central docker.io
sudo systemctl enable --now openvswitch-switch ovn-central 

# Set OVN DB connections
sudo ovn-nbctl set-connection ptcp:6641:0.0.0.0
sudo ovn-sbctl set-connection ptcp:6642:0.0.0.0

# --- 3. OVN Logical Networking ---
sudo ovn-nbctl ls-add ls-test

# Create container ports
for i in {1..4}; do
    sudo ovn-nbctl lsp-add ls-test lp-host$i
    sudo ovn-nbctl lsp-set-addresses lp-host$i "02:00:00:00:00:0$i 10.0.0.$i/24"
done

# Create ONE localnet port for the whole switch
# On a single node, this acts as the anchor for the logical switch
sudo ovn-nbctl lsp-add ls-test ln-port
sudo ovn-nbctl lsp-set-type ln-port localnet
sudo ovn-nbctl lsp-set-addresses ln-port unknown
sudo ovn-nbctl lsp-set-options ln-port network_name=physnet

# --- 4. Configure OVS & Bridge Mappings ---
sudo ovs-vsctl set open . external-ids:system-id=ovs-host
sudo ovs-vsctl set open . external-ids:ovn-remote=tcp:127.0.0.1:6642
sudo ovs-vsctl set open . external-ids:ovn-encap-type=geneve
sudo ovs-vsctl set open . external-ids:ovn-encap-ip=127.0.0.1

# Map 'physnet' to br-ovs1 (this is your primary provider bridge)
sudo ovs-vsctl set open . external-ids:ovn-bridge-mappings=physnet:br-ovs1

# Create your bridges
sudo ovs-vsctl add-br br-ovs1
sudo ovs-vsctl add-br br-ovs2

# --- NEW: Manually Patch br-ovs1 and br-ovs2 ---
# Since OVN only manages the mapping for ONE bridge, 
# we manually link br-ovs1 and br-ovs2 so they act as one fabric.
sudo ovs-vsctl \
    -- add-port br-ovs1 patch-ovs1-to-ovs2 -- set interface patch-ovs1-to-ovs2 type=patch options:peer=patch-ovs2-to-ovs1 \
    -- add-port br-ovs2 patch-ovs2-to-ovs1 -- set interface patch-ovs2-to-ovs1 type=patch options:peer=patch-ovs1-to-ovs2

# --- 5. Container & Veth Setup ---
for i in {1..4}; do
    sudo ip link add veth$i type veth peer name veth$i-c
    sudo ip link set veth$i up
done

# Attach veths to your chosen bridges
sudo ovs-vsctl add-port br-ovs1 veth1 -- set Interface veth1 external-ids:iface-id=lp-host1
sudo ovs-vsctl add-port br-ovs1 veth2 -- set Interface veth2 external-ids:iface-id=lp-host2
sudo ovs-vsctl add-port br-ovs2 veth3 -- set Interface veth3 external-ids:iface-id=lp-host3
sudo ovs-vsctl add-port br-ovs2 veth4 -- set Interface veth4 external-ids:iface-id=lp-host4

for i in {1..4}; do
    sudo docker run -dit --name host$i --net=none --privileged alpine sh
    PID=$(sudo docker inspect -f '{{.State.Pid}}' host$i)
    sudo ip link set veth$i-c netns $PID
    sudo nsenter -t $PID -n ip link set veth$i-c name eth0
    sudo nsenter -t $PID -n ip addr add 10.0.0.$i/24 dev eth0
    sudo nsenter -t $PID -n ip link set eth0 address 02:00:00:00:00:0$i
    sudo nsenter -t $PID -n ip link set eth0 up
done

# --- 6. Verification ---
echo "Waiting for OVN flows (5s)..."
sleep 5
echo "Testing connectivity host1 -> host4..."
sudo docker exec host1 ping -c 3 10.0.0.4

#Ping test
for i in {1..4}; do
    sudo docker exec host1 ping -c 3 10.0.0.$i
done

#Useful debug command
sudo ovn-nbctl show
sudo ovn-sbctl show
sudo ovs-vsctl show
sudo ovs-ofctl dump-flows br-ovs1