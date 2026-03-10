import swsssdk

def manage_sonic_network():
    # 1. Connect to the Configuration Database (ConfigDB)
    # SONiC uses specific database IDs (e.g., ConfigDB is usually DB 4)
    config_db = swsssdk.SonicV2Connector(host='127.0.0.1')
    config_db.connect(config_db.CONFIG_DB)

    print("--- Fetching Interface Data ---")
    
    # 2. Get all Ethernet interfaces
    interfaces = config_db.get_all(config_db.CONFIG_DB, "INTERFACE")
    
    if not interfaces:
        print("No interfaces found or not running on a SONiC node.")
        return

    for intf_name in interfaces:
        print(f"Interface: {intf_name}")
        # Fetch specific details like IP address
        details = config_db.get_all(config_db.CONFIG_DB, f"INTERFACE|{intf_name}")
        print(f"  Details: {details}")

    # 3. Update an Interface (e.g., setting an admin status)
    # Caution: This modifies live network config
    target_intf = "Ethernet0"
    config_db.set_entry(config_db.CONFIG_DB, f"PORT|{target_intf}", {"admin_status": "up"})
    print(f"\nAdmin status for {target_intf} set to 'up'.")

if __name__ == "__main__":
    manage_sonic_network()