#Config FRR Alpine Router
docker pull alpine:latest

#cleanup
sudo docker stop router1 C1 C2 C3 C4
sudo docker rm router1 C1 C2 C3 C4
sudo docker network rm routernet
sudo ovs-vsctl del-br ovs1
sudo ovs-vsctl del-br ovs2

#setup docker network
sudo docker network create --subnet=172.20.0.0/16 routernet

#create router1, router2, mypc1, mypc2, mypc3, mypc4, mypc5, mypc6
sudo docker run -dit --name router1 --hostname router1 \
--network routernet --ip 172.20.0.10 \
--privileged \
alpine:latest

sudo docker run -itd --name mypc1 --net=none --privileged alpine:latest sh 
sudo docker run -itd --name mypc2 --net=none --privileged alpine:latest sh 
sudo docker run -itd --name mypc3 --net=none --privileged alpine:latest sh 
sudo docker run -itd --name mypc4 --net=none --privileged alpine:latest sh
sudo docker run -itd --name mypc5 --net=none --privileged alpine:latest sh
sudo docker run -itd --name mypc6 --net=none --privileged alpine:latest sh


sudo ovs-vsctl add-br ovs1
sudo ovs-vsctl add-br ovs2

#wiring

#leftside
# Subnets: 172.16.0.1/16
# Connect mypc1, mypc2, mypc3 to OVS1
sudo ovs-docker add-port ovs1 eth0 mypc1 --ipaddress=172.16.1.1/24 --gateway=172.16.1.10
sudo ovs-vsctl show
sudo ovs-docker add-port ovs1 eth0 mypc2 --ipaddress=172.16.2.10/24 --gateway=172.16.2.10
sudo ovs-vsctl show
sudo ovs-docker add-port ovs1 eth0 mypc3 --ipaddress=192.168.3.10/24 --gateway=192.168.3.1

# Connect R1 to OVS1
# Assign Gateway IP for mypc1 (.1.1) to interface eth1
sudo ovs-docker add-port ovs1 eth1 router1 --ipaddress=192.168.1.1/24

# Add Secondary IP for mypc2 (.2.1) to same interface
sudo docker exec router1 ip addr add 192.168.2.1/24 dev eth1
sudo docker exec router1 ip link set eth1 up

# Add Secondary IP for mypc3 (.3.1) to same interface
sudo docker exec router1 ip addr add 192.168.3.1/24 dev eth1
sudo docker exec router1 ip link set eth1 up

#rightside
# Subnets: 192.168.3.0/24 and 192.168.4.0/24 (Unique!)
# Connect mypc4, mypc5, mypc6 to OVS2
sudo ovs-docker add-port ovs2 eth0 mypc4 --ipaddress=192.168.3.20/24 --gateway=192.168.3.1
sudo ovs-vsctl show
sudo ovs-docker add-port ovs2 eth0 mypc5 --ipaddress=192.168.4.20/24 --gateway=192.168.4.1
sudo ovs-vsctl show
sudo ovs-docker add-port ovs2 eth0 mypc6 --ipaddress=192.168.5.20/24 --gateway=192.168.5.1
sudo ovs-vsctl show

# Connect R2 to OVS2
# Add Secondary IP for mypc4 (.4.1) to same interface
sudo docker exec router2 ip addr add 192.168.4.1/24 dev eth1
sudo docker exec router2 ip link set eth1 up

# Add Secondary IP for mypc5 (.5.1) to same interface
sudo docker exec router2 ip addr add 192.168.5.1/24 dev eth1
sudo docker exec router2 ip link set eth1 up

# Add Secondary IP for mypc6 (.6.1) to same interface
sudo docker exec router2 ip addr add 192.168.6.1/24 dev eth1
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

#Check ospf
sudo docker exec router1 vtysh -c "show ip ospf neighbor"
sudo docker exec router1 vtysh -c "show ip route"
sudo docker exec router2 vtysh -c "show ip ospf neighbor"
sudo docker exec router2 vtysh -c "show ip route"


#ping test
sudo docker exec mypc1 ping 192.168.2.10 -c 5
sudo docker exec mypc1 ping 192.168.3.20 -c 5
sudo docker exec mypc1 ping 192.168.4.20 -c 5
sudo docker exec mypc1 ping 192.168.5.20 -c 5
sudo docker exec mypc1 ping 192.168.6.20 -c 5

#Now



