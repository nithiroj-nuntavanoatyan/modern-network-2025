#Create mininet network topology without controller
sudo mn --topo tree,2 --mac --arp --switch ovsk

#mininet CLI will start after this command

#Check nodes
mininet> nodes

#Check topology
mininet> net

#Check links
mininet> links

#Check link connections between host and switch and result
mininet> dump

#Check interfaces of h1
mininet> h1 ifconfig

#Check connection between host1 and host2 3 times
mininet> h1 ping -c 3 h2

#Test ping between all hosts
mininet> pingall

#Test ping pair
mininet> pingpair

#Test bandwith between h1 and h4
mininet> iperf h1 h4

#Check H1 ARP
mininet> h1 arp

#Show OVS bridges
mininet> sh ovs-vsctl show

#Show openflow in bridges
mininet> sh ovs-ofctl show s1

#Exit mininet CLI
mininet> exit

