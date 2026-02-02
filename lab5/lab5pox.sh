#open in another tab
sudo mn --mac --switch=ovsk --controller=remote,ip=127.0.0.1,port=6633
dpctl dump-flows
h1 arp
h1 ping -c h2
#open in another tab
sudo wireshark
#open in another tab
cd pox
sudo ./pox.py --verbose forwarding.l2_learning