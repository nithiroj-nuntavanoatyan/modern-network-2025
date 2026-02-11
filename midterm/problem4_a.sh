#Add bridge ovs-mybr and config ip address
sudo ovs-vsctl add-br ovs-mybr
sudo ifconfig ovs-mybr 172.16.0.10 netmask 255.255.0.0 up
sudo ifconfig ovs-mybr

#Create 4 alpine containers with privileged mode
sudo docker run -dt --name mypc1 --privileged alpine:latest
sudo docker run -dt --name mypc2 --privileged alpine:latest
sudo docker run -dt --name mypc3 --privileged alpine:latest
sudo docker run -dt --name mypc4 --privileged alpine:latest
sudo docker run -dt --name mypc5 --privileged alpine:latest
sudo docker run -dt --name mypc6 --privileged alpine:latest

#Check docker
sudo docker exec mypc1 ip link list

#Connect containers to ovs-mybr with specific ip addresses with 172.16.0.1/16 subnet
sudo ovs-docker add-port ovs-mybr eth1 mypc1 --ipaddress=172.16.0.1/16
sudo ovs-docker add-port ovs-mybr eth1 mypc2 --ipaddress=172.16.0.2/16
sudo ovs-docker add-port ovs-mybr eth1 mypc3 --ipaddress=172.16.0.3/16
sudo ovs-docker add-port ovs-mybr eth1 mypc4 --ipaddress=172.16.0.4/16
sudo ovs-docker add-port ovs-mybr eth1 mypc5 --ipaddress=172.16.0.5/16
sudo ovs-docker add-port ovs-mybr eth1 mypc6 --ipaddress=172.16.0.6/16

#Check docker network
sudo docker exec mypc1 ip link list

#Check OVS
sudo ovs-vsctl show

#Check forwarding database
sudo ovs-appctl fdb/show ovs-mybr

#Test connectivity between containers
sudo docker exec mypc1 ping -c 3 172.16.0.2

#Check forwarding database again
sudo ovs-appctl fdb/show ovs-mybr

#Test connectivity between containers
sudo docker exec mypc1 ping -c 3 172.16.0.2
sudo docker exec mypc1 ping -c 3 172.16.0.3
sudo docker exec mypc1 ping -c 3 172.16.0.4
sudo docker exec mypc1 ping -c 3 172.16.0.5
sudo docker exec mypc1 ping -c 3 172.16.0.6

#Check forwarding database again
sudo ovs-appctl fdb/show ovs-mybr

#Config vlan
sudo ovs-vsctl set port 05d0731c137c4_l tag=10
sudo ovs-vsctl set port 4fb250cf3ec54_l tag=10
sudo ovs-vsctl set port 3bb4a933c5814_l tag=20
sudo ovs-vsctl set port 3ed9346383a64_l tag=20
sudo ovs-vsctl set port f49dfcc02c564_l tag=30
sudo ovs-vsctl set port f4f16e6892fa4_l tag=30
sudo ovs-vsctl show
sudo ovs-appctl fdb/show ovs-mybr

#Ping test mypc1 to all other containers
sudo docker exec mypc1 ping -c 3 172.16.0.2
sudo docker exec mypc1 ping -c 3 172.16.0.3
sudo docker exec mypc1 ping -c 3 172.16.0.4
sudo docker exec mypc1 ping -c 3 172.16.0.5
sudo docker exec mypc1 ping -c 3 172.16.0.6

#Ping test mypc2 to all other containers
sudo docker exec mypc2 ping -c 3 172.16.0.1
sudo docker exec mypc2 ping -c 3 172.16.0.3
sudo docker exec mypc2 ping -c 3 172.16.0.4
sudo docker exec mypc2 ping -c 3 172.16.0.5
sudo docker exec mypc2 ping -c 3 172.16.0.6

#Ping test mypc3 to all other containers
sudo docker exec mypc3 ping -c 3 172.16.0.1
sudo docker exec mypc3 ping -c 3 172.16.0.2
sudo docker exec mypc3 ping -c 3 172.16.0.4
sudo docker exec mypc3 ping -c 3 172.16.0.5
sudo docker exec mypc3 ping -c 3 172.16.0.6

#Check flow table
sudo ovs-ofctl dump-flows ovs-mybr

#Cleanup
sudo docker stop mypc1 mypc2 mypc3 mypc4 mypc5 mypc6
sudo docker rm mypc1 mypc2 mypc3 mypc4 mypc5 mypc6
sudo ovs-vsctl del-br ovs-mybr
sudo ovs-vsctl show
