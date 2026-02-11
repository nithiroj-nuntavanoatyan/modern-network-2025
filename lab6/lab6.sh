#Install SR Linux image
sudo docker pull ghcr.io/nokia/srlinux:latest

#Create a Containerlab topology file
nano project.clab.yml

#Inside project.clab.yml, add the following content:
name: project

name: project

topology:
  nodes:
    srl1:
      kind: nokia_srlinux
      image: ghcr.io/nokia/srlinux:latest
    srl2:
      kind: nokia_srlinux
      image: ghcr.io/nokia/srlinux:latest
  links:
    - endpoints: ["srl1:e1-1", "srl2:e1-1"]

#Deploy the Containerlab topology
sudo containerlab deploy +
#After deployment, you should see two docker containers running: clab-project-srl1 and clab-project-srl2
#verify the topology
sudo containerlab inspect
#There will be a new clab-project folder created in your current directory

#Check docker containers
sudo docker ps -a

#Ping test
ping 172.20.20.2 -c 3
ping 172.20.20.3 -c 3

#Set docker container configurations
sudo docker exec clab-project-srl1 bash -c "printf 'PermitRootLogin yes\nPasswordAuthentication yes\nPubkeyAuthentication yes\nUsePAM yes\n' > /etc/ssh/sshd_config_mgmt"
sudo docker exec clab-project-srl2 bash -c "printf 'PermitRootLogin yes\nPasswordAuthentication yes\nPubkeyAuthentication yes\nUsePAM yes\n' > /etc/ssh/sshd_config_mgmt"

sudo docker exec clab-project-srl1 bash -c "pkill sshd; sleep 2; /usr/sbin/sshd"
sudo docker exec clab-project-srl2 bash -c "pkill sshd; sleep 2; /usr/sbin/sshd"

#In case not knowing ansible_ssh_pass
sudo docker exec -it clab-project-srl1 bash
passwd
asdw5678
exit
sudo docker exec -it clab-project-srl2 bash
passwd
asdw5678
exit

#Test SSH connection
ssh root@172.20.20.2

quit, exit
ssh root@172.20.20.3

quit, exit

#if any issue with SSH connection, restart the containers
ssh-keygen -f "/home/$USER/.ssh/known_hosts" -R "172.20.20.2"
ssh-keygen -f "/home/$USER/.ssh/known_hosts" -R "172.20.20.3"

#Ansible ping all
ansible -i lab6/hosts.ini all -m ansible.builtin.ping

#Test srlinux CLI use username and password in lab6/clab-project/ansible-inventory.yml
ssh admin@172.20.20.2
NokiaSrl1!
show version
show network-instance route-table all
show platform
show interface
quit
