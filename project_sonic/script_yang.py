from pygnmi.client import gNMIclient

# Switch Credentials
target = ('172.20.20.2', 8080)  # IP and default gNMI port
creds = ('admin', 'YourPassword')

def get_sonic_state():
    # Define the path using YANG notation
    # This specific path looks at the operational state of Ethernet0
    paths = ['openconfig-interfaces:interfaces/interface[name=Ethernet0]/state']

    with gNMIclient(target=target, username=creds[0], password=creds[1], insecure=True) as gc:
        # Fetch data from the switch
        result = gc.get(path=paths)
        
        # Parse and print the operational status
        try:
            if_state = result['notification'][0]['update'][0]['val']
            print(f"Interface Ethernet0 Status: {if_state.get('oper-status')}")
            print(f"MTU: {if_state.get('mtu')}")
        except (KeyError, IndexError):
            print("Could not retrieve interface data. Check your YANG path.")

if __name__ == "__main__":
    get_sonic_state()