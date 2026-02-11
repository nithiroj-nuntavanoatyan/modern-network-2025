#Create network namespace netspace_1, netspace_2, netspace_3
sudo ip netns add netspace_1
sudo ip netns add netspace_2
sudo ip netns add netspace_3

#Create veth veth1 and veth2 along with ovs_veth1, ovs_veth2, ovs_veth3
sudo ip link add veth1 type veth peer name ovs_veth1
sudo ip link add veth2 type veth peer name ovs_veth2
sudo ip link add veth3 type veth peer name ovs_veth3
sudo ip link list

#Assign veth1 to netspace_1 and veth2 to netspace_2 and veth3 to netspace_3 then change their state to up and configure IP addresses (Class B:)
sudo ip link set veth1 netns netspace_1
sudo ip link set veth2 netns netspace_2
sudo ip link set veth3 netns netspace_3
sudo ip netns exec netspace_1 ip link set veth1 up
sudo ip netns exec netspace_2 ip link set veth2 up
sudo ip netns exec netspace_3 ip link set veth3 up
sudo ip netns exec netspace_1 ip addr add 172.16.1.1/24 dev veth1
sudo ip netns exec netspace_2 ip addr add 172.16.1.2/24 dev veth2
sudo ip netns exec netspace_3 ip addr add 172.16.1.3/24 dev veth3

#Test ping between netspace_1 and netspace_2 (should fail)
sudo ip netns exec netspace_1 ping -c 3 172.16.1.2

#Check OVS show
sudo ovs-vsctl show

#Create OVS bridge ovs_br then add ovs_veth1, ovs_veth2, ovs_veth3 to it, then change their state to up
sudo ovs-vsctl add-br ovs_br
sudo ip link set ovs_veth1 up
sudo ip link set ovs_veth2 up
sudo ip link set ovs_veth3 up
sudo ovs-vsctl add-port ovs_br ovs_veth1
sudo ovs-vsctl add-port ovs_br ovs_veth2
sudo ovs-vsctl add-port ovs_br ovs_veth3
sudo ovs-vsctl show

#Test ping between netspace_1 and netspace_2 and ping between netspace_2 and netspace_3 (should work now)
sudo ip netns exec netspace_1 ping -c 3 172.16.1.2
sudo ip netns exec netspace_2 ping -c 3 172.16.1.3

#Check forwarding database in OVS
sudo ovs-appctl fdb/show ovs_br

#Delete network namespaces
sudo ip netns del netspace_1
sudo ip netns del netspace_2
sudo ip netns del netspace_3

#Cleanup OVS
sudo ovs-vsctl del-br ovs_br
sudo ip link del ovs_veth1
sudo ip link del ovs_veth2
sudo ip link del ovs_veth3

#Final OVS show
sudo ovs-vsctl show