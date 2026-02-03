#Config FRR Alpine Router
docker pull alpine:latest

#cleanup
sudo docker stop router1 router2 C1 C2 C3 C4
sudo docker rm router1 router2 C1 C2 C3 C4
sudo docker network rm routernet
sudo ovs-vsctl del-br ovs1
sudo ovs-vsctl del-br ovs2

#setup docker network
sudo docker network create --subnet=172.20.0.0/16 routernet

#create router1, router2, C1, C2, C3, C4
sudo docker run -dit --name router1 --hostname router1 \
--network routernet --ip 172.20.0.2 \
--privileged \
alpine:latest

sudo docker run -dit --name router2 --hostname router2 \
--network routernet --ip 172.20.0.3 \
--privileged \
alpine:latest 

sudo docker run -itd --name C1 --net=none --privileged alpine:latest sh 
sudo docker run -itd --name C2 --net=none --privileged alpine:latest sh 
sudo docker run -itd --name C3 --net=none --privileged alpine:latest sh 
sudo docker run -itd --name C4 --net=none --privileged alpine:latest sh 

sudo ovs-vsctl add-br ovs1
sudo ovs-vsctl add-br ovs2

#wiring

#leftside
# Subnets: 192.168.1.0/24 and 192.168.2.0/24
# Connect C1 & C2 to OVS1
sudo ovs-docker add-port ovs1 eth0 C1 --ipaddress=192.168.1.10/24 --gateway=192.168.1.1
sudo ovs-vsctl show
sudo ovs-docker add-port ovs1 eth0 C2 --ipaddress=192.168.2.10/24 --gateway=192.168.2.1
sudo ovs-vsctl show

# Connect R1 to OVS1
# Assign Gateway IP for C1 (.1.1) to interface eth1
sudo ovs-docker add-port ovs1 eth1 router1 --ipaddress=192.168.1.1/24

# Add Secondary IP for C2 (.2.1) to same interface
sudo docker exec router1 ip addr add 192.168.2.1/24 dev eth1
sudo docker exec router1 ip link set eth1 up

#rightside
# Subnets: 192.168.3.0/24 and 192.168.4.0/24 (Unique!)
# Connect C3 & C4 to OVS2
sudo ovs-docker add-port ovs2 eth0 C3 --ipaddress=192.168.3.20/24 --gateway=192.168.3.1
sudo ovs-vsctl show
sudo ovs-docker add-port ovs2 eth0 C4 --ipaddress=192.168.4.20/24 --gateway=192.168.4.1
sudo ovs-vsctl show

# Connect R2 to OVS2
# Assign Gateway IP for C3 (.3.1) to interface eth1
sudo ovs-docker add-port ovs2 eth1 router2 --ipaddress=192.168.3.1/24

# Add Secondary IP for C4 (.4.1) to same interface
sudo docker exec router2 ip addr add 192.168.4.1/24 dev eth1
sudo docker exec router2 ip link set eth1 up

#Router1 configuration
sudo docker exec -it router1 sh
apk update && apk add frr frr-openrc ip6tables iptables net-tools
iptables -P FORWARD ACCEPT
sed -i s/ospfd=no/ospfd=yes/ /etc/frr/daemons
sed -i s/zebra=no/zebra=yes/ /etc/frr/daemons
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

/usr/lib/frr/frrinit.sh start
vtysh
conf t
router ospf
network 172.20.0.0/16 area 0
network 192.168.1.0/24 area 0
network 192.168.2.0/24 area 0
exit
exit
write memory

#Router2 configuration
sudo docker exec -it router2 sh
apk update && apk add frr frr-openrc ip6tables iptables net-tools
iptables -P FORWARD ACCEPT
sed -i s/ospfd=no/ospfd=yes/ /etc/frr/daemons
sed -i s/zebra=no/zebra=yes/ /etc/frr/daemons
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

/usr/lib/frr/frrinit.sh start
vtysh
conf t
router ospf
network 172.20.0.0/16 area 0
network 192.168.3.0/24 area 0
network 192.168.4.0/24 area 0
exit
exit
write memory

#Check ospf
sudo docker exec router1 vtysh -c "show ip ospf neighbor"
sudo docker exec router1 vtysh -c "show ip route"
sudo docker exec router2 vtysh -c "show ip ospf neighbor"
sudo docker exec router2 vtysh -c "show ip route"


#ping test
sudo docker exec C1 ping 192.168.2.10 -c 5
sudo docker exec C1 ping 192.168.3.20 -c 5
sudo docker exec C1 ping 192.168.4.20 -c 5



