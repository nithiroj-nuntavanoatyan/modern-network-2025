#open in another tab
cd pox
sudo ./pox.py --verbose forwarding.l2_learning

#open in another tab
#Create a simple topology with 1 switch and 4 hosts with controller
sudo mn --topo tree,2 --mac --switch=ovsk --controller=remote,ip=127.0.0.1,port=6633
sudo mn --topo single,4 --mac --switch=ovsk --controller=remote,ip=127.0.0.1,port=6633
dpctl dump-flows
h1 arp
h1 ping -c 3 h2
h1 ping -c 3 h3
h1 ping -c 3 h4

#open in another tab
sudo wireshark
