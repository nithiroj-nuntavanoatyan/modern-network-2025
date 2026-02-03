#Add bridge ovs-mybr and config ip address
sudo ovs-vsctl add-br ovs-mybr
sudo ifconfig ovs-mybr 192.168.1.1 netmask 255.255.255.0 up
sudo ifconfig ovs-mybr

#Create 4 alpine containers with privileged mode
sudo docker run -dt --name mypc1 --privileged alpine:latest sleep 1d
sudo docker run -dt --name mypc2 --privileged alpine:latest sleep 1d
sudo docker run -dt --name mypc3 --privileged alpine:latest sleep 1d
sudo docker run -dt --name mypc4 --privileged alpine:latest sleep 1d

#Check docker
sudo docker exec mypc1 ip link list

#Connect containers to ovs-mybr with specific ip addresses
sudo ovs-docker add-port ovs-mybr eth1 mypc1 --ipaddress=192.168.1.10/24
sudo ovs-docker add-port ovs-mybr eth1 mypc2 --ipaddress=192.168.1.20/24
sudo ovs-docker add-port ovs-mybr eth1 mypc3 --ipaddress=192.168.1.30/24
sudo ovs-docker add-port ovs-mybr eth1 mypc4 --ipaddress=192.168.1.40/24

#Check docker network
sudo docker exec mypc1 ip link list

#Check OVS
sudo ovs-vsctl show

#Check forwarding database
sudo ovs-appctl fdb/show ovs-mybr

#Test connectivity between containers
sudo docker exec mypc1 ping -c 3 192.168.1.20

#Check forwarding database again
sudo ovs-appctl fdb/show ovs-mybr

#Test connectivity between containers
sudo docker exec mypc1 ping -c 3 192.168.1.30
sudo docker exec mypc1 ping -c 3 192.168.1.40

#Check forwarding database again
sudo ovs-appctl fdb/show ovs-mybr

#Config vlan
sudo ovs-vsctl set port 98edf1d9aee84_l tag=10
sudo ovs-vsctl set port 5c8e6c48bf0d4_l tag=10
sudo ovs-vsctl set port 5de2b0aa897b4_l tag=20
sudo ovs-vsctl set port 7f12065cdb284_l tag=20
sudo ovs-vsctl show
sudo ovs-appctl fdb/show ovs-mybr

#Ping test
sudo docker exec mypc1 ping -c 3 192.168.1.20
sudo docker exec mypc1 ping -c 3 192.168.1.30
sudo docker exec mypc1 ping -c 3 192.168.1.40

#Check flow table
sudo ovs-ofctl dump-flows ovs-mybr

#Cleanup
sudo docker stop mypc1 mypc2 mypc3 mypc4
sudo docker rm mypc1 mypc2 mypc3 mypc4
sudo ovs-vsctl del-br ovs-mybr
sudo ovs-vsctl show
