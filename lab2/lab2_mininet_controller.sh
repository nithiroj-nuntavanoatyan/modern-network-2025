#Create mininet network topology with controller
sudo mn --topo tree,2 --mac --arp --switch ovsk --controller


#--controller=remote,ip=<controller_ip>,port=<controller_port>
mininet> sh ovs-vsctl show

#mininet CLI will start after this command

#Check nodes
mininet> nodes

#Check topology
mininet> net

#Check links
mininet> links

#Check link connections between host and switch and result
mininet> dump

#Add flow entry to switch s1
sh ovs-ofctl add-flow s1 in_port=1,actions=output:2
sh ovs-ofctl add-flow s1 in_port=2,actions=output:1

#Check flow entries in switch s1
sh ovs-ofctl dump-flows s1

#Add flow entry to switch s2
sh ovs-ofctl add-flow s2 in_port=1,actions=output:2,3
sh ovs-ofctl add-flow s2 in_port=2,actions=output:1,3
sh ovs-ofctl add-flow s2 in_port=3,actions=output:1,2

#Check flow entries in switch s2
sh ovs-ofctl dump-flows s2

#Add flow entry to switch s3
sh ovs-ofctl add-flow s3 in_port=1,actions=output:2,3
sh ovs-ofctl add-flow s3 in_port=2,actions=output:1,3
sh ovs-ofctl add-flow s3 in_port=3,actions=output:1,2

#Check flow entries in switch s3
sh ovs-ofctl dump-flows s3

h1 ping -c 3 h2
h1 ping -c 3 h3
h1 ping -c 3 h4

#Test ping between all hosts
pingall