#!/usr/bin/env python3
"""
SONiC Remote Redis Agent
Runs on YOUR PC — connects to SONiC via SSH tunnel automatically.

Requirements:
    pip install redis paramiko

Usage:
    python3 sonic_remote.py
"""

import redis
import json
import sys
import time
import threading
import paramiko
import socket

# ─────────────────────────────────────────────
# CONFIG — edit these to match your setup
# ─────────────────────────────────────────────
SONIC_HOST     = "172.20.20.2"       # SONiC management IP
SONIC_SSH_PORT = 22
SONIC_USER     = "root"
SONIC_PASSWORD = "sonic123"      # change if different
SONIC_SOCKET   = "/run/redis/redis.sock"

LOCAL_TUNNEL_PORT = 16379            # local port for the tunnel (avoid conflict with local redis)

# ─────────────────────────────────────────────
# SONiC DB map
# ─────────────────────────────────────────────
SONIC_DBS = {
    "APPL_DB":        0,
    "ASIC_DB":        1,
    "COUNTERS_DB":    2,
    "LOGLEVEL_DB":    3,
    "CONFIG_DB":      4,
    "PFC_WD_DB":      5,
    "STATE_DB":       6,
    "SNMP_OVERLAY_DB":7,
    "ERROR_DB":       8,
}

# ─────────────────────────────────────────────
# SSH Tunnel via Paramiko (no manual terminal needed)
# ─────────────────────────────────────────────
class SSHTunnel:
    """
    Opens an SSH tunnel from localhost:LOCAL_TUNNEL_PORT
    → SONiC Unix socket /run/redis/redis.sock
    entirely in Python — no manual ssh command needed.
    """
    def __init__(self):
        self.ssh     = None
        self.running = False
        self.threads = []

    def connect(self):
        print(f"[SSH] Connecting to {SONIC_USER}@{SONIC_HOST}:{SONIC_SSH_PORT} ...")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh.connect(
                hostname=SONIC_HOST,
                port=SONIC_SSH_PORT,
                username=SONIC_USER,
                password=SONIC_PASSWORD,
                timeout=10,
            )
            print("[SSH] Connected ✓")
        except Exception as e:
            print(f"[SSH] Failed to connect: {e}")
            sys.exit(1)

    def _forward_handler(self, client_sock):
        """Forward one client connection to the SONiC Unix socket via SSH."""
        try:
            transport = self.ssh.get_transport()
            # open a direct channel to the Unix socket on the remote side
            chan = transport.open_channel(
                "direct-tcpip",
                dest_addr=(SONIC_SOCKET, 0),   # remote Unix socket (treated as host:0)
                src_addr=("127.0.0.1", LOCAL_TUNNEL_PORT),
            )
        except Exception as e:
            print(f"[TUNNEL] Channel error: {e}")
            client_sock.close()
            return

        def pump(src, dst):
            try:
                while True:
                    data = src.recv(4096)
                    if not data:
                        break
                    dst.sendall(data)
            except Exception:
                pass
            finally:
                try: src.close()
                except: pass
                try: dst.close()
                except: pass

        t1 = threading.Thread(target=pump, args=(client_sock, chan),  daemon=True)
        t2 = threading.Thread(target=pump, args=(chan, client_sock),  daemon=True)
        t1.start(); t2.start()
        t1.join();  t2.join()

    def start(self):
        """Start local TCP listener that forwards to SONiC Redis socket."""
        self.running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", LOCAL_TUNNEL_PORT))
        server.listen(10)
        server.settimeout(1)
        print(f"[TUNNEL] Listening on 127.0.0.1:{LOCAL_TUNNEL_PORT} → {SONIC_HOST}:{SONIC_SOCKET}")

        def accept_loop():
            while self.running:
                try:
                    client_sock, _ = server.accept()
                    t = threading.Thread(
                        target=self._forward_handler,
                        args=(client_sock,),
                        daemon=True,
                    )
                    t.start()
                    self.threads.append(t)
                except socket.timeout:
                    continue
                except Exception:
                    break
            server.close()

        t = threading.Thread(target=accept_loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False
        if self.ssh:
            self.ssh.close()
        print("[SSH] Tunnel closed.")


# ─────────────────────────────────────────────
# Redis connection (always via tunnel)
# ─────────────────────────────────────────────
def connect(db_id: int) -> redis.Redis:
    return redis.Redis(
        host="127.0.0.1",
        port=LOCAL_TUNNEL_PORT,
        db=db_id,
        socket_connect_timeout=5,
        decode_responses=True,
    )

def list_keys(r, pattern="*", count=100):
    return list(r.scan_iter(pattern, count=count))

def pretty(data):
    return json.dumps(data, indent=2, default=str)


# ─────────────────────────────────────────────
# Feature functions
# ─────────────────────────────────────────────
def dump_config_db():
    r = connect(4)
    tables = ["PORT|*", "VLAN|*", "BGP_NEIGHBOR|*", "DEVICE_METADATA|*",
              "INTERFACE|*", "LOOPBACK_INTERFACE|*"]
    for pattern in tables:
        keys = list_keys(r, pattern)
        if not keys:
            continue
        print(f"\n{'='*60}\n  CONFIG_DB · {pattern}\n{'='*60}")
        for k in sorted(keys)[:20]:
            val = r.hgetall(k)
            print(f"\n  [{k}]")
            for field, v in val.items():
                print(f"    {field:<30} = {v}")


def dump_appl_db_routes():
    r = connect(0)
    keys = list_keys(r, "ROUTE_TABLE:*", count=200)
    print(f"\n{'='*60}\n  APPL_DB · ROUTE_TABLE ({len(keys)} entries)\n{'='*60}")
    for k in sorted(keys)[:50]:
        val = r.hgetall(k)
        print(f"  {k:<45}  nexthop={val.get('nexthop','?')}  ifname={val.get('ifname','?')}")


def dump_counters_db():
    r = connect(2)
    name_map = r.hgetall("COUNTERS_PORT_NAME_MAP")
    print(f"\n{'='*60}\n  COUNTERS_DB · Port Counters\n{'='*60}")
    for port, oid in sorted(name_map.items()):
        c      = r.hgetall(f"COUNTERS:{oid}")
        rx     = c.get("SAI_PORT_STAT_IF_IN_OCTETS",  "N/A")
        tx     = c.get("SAI_PORT_STAT_IF_OUT_OCTETS", "N/A")
        rx_err = c.get("SAI_PORT_STAT_IF_IN_ERRORS",  "0")
        tx_err = c.get("SAI_PORT_STAT_IF_OUT_ERRORS", "0")
        print(f"  {port:<15}  RX={rx:>15} B   TX={tx:>15} B   RX_ERR={rx_err}  TX_ERR={tx_err}")


def dump_state_db():
    r = connect(6)
    keys = list_keys(r, "PORT_TABLE:*")
    print(f"\n{'='*60}\n  STATE_DB · PORT_TABLE ({len(keys)} ports)\n{'='*60}")
    for k in sorted(keys):
        val = r.hgetall(k)
        print(f"  {k:<35}  oper={val.get('oper_status','?'):<5}  speed={val.get('speed','?')}")


def dump_all_interfaces():
    cfg  = connect(4)
    appl = connect(0)
    stat = connect(6)

    names = set()
    for k in list_keys(cfg,  "PORT|*"):        names.add(k.split("|",1)[1])
    for k in list_keys(appl, "PORT_TABLE:*"):  names.add(k.split(":",1)[1])
    for k in list_keys(stat, "PORT_TABLE:*"):  names.add(k.split(":",1)[1])

    print(f"\n{'='*70}\n  INTERFACE STATUS\n{'='*70}")
    for iface in sorted(names):
        cfg_data  = cfg.hgetall(f"PORT|{iface}")
        appl_data = appl.hgetall(f"PORT_TABLE:{iface}")
        stat_data = stat.hgetall(f"PORT_TABLE:{iface}")

        ip_keys      = list(cfg.scan_iter(f"INTERFACE|{iface}|*"))
        appl_ip_keys = list(appl.scan_iter(f"INTF_TABLE:{iface}:*"))
        ips      = [k.split("|",2)[2] for k in ip_keys]
        appl_ips = [k.split(":",2)[2] for k in appl_ip_keys]

        admin = cfg_data.get("admin_status", appl_data.get("admin_status", "?"))
        oper  = stat_data.get("oper_status", "?")
        speed = stat_data.get("speed", cfg_data.get("speed", "?"))
        mtu   = cfg_data.get("mtu", appl_data.get("mtu", "?"))
        desc  = cfg_data.get("description", "")

        print(f"\n  Interface : {iface}  {f'« {desc} »' if desc else ''}")
        print(f"  ├─ Admin  : {'✅' if admin=='up' else '🔴'} {admin}")
        print(f"  ├─ Oper   : {'✅' if oper=='up'  else '🔴'} {oper}")
        print(f"  ├─ Speed  : {speed} Mbps    MTU: {mtu}")
        print(f"  ├─ IP cfg : {', '.join(ips)      if ips      else '(none)'}")
        print(f"  └─ IP app : {', '.join(appl_ips) if appl_ips else '(not applied yet)'}")


def inspect_one_interface():
    iface = input("Interface name (e.g. Ethernet0) > ").strip()
    cfg  = connect(4)
    appl = connect(0)
    stat = connect(6)

    for label, r, key in [
        ("CONFIG_DB", cfg,  f"PORT|{iface}"),
        ("APPL_DB",   appl, f"PORT_TABLE:{iface}"),
        ("STATE_DB",  stat, f"PORT_TABLE:{iface}"),
    ]:
        print(f"\n{'='*60}\n  {label} → {key}\n{'='*60}")
        data = r.hgetall(key)
        if data:
            for f, v in data.items():
                print(f"  {f:<30} = {v}")
        else:
            print("  (no entry)")

    print(f"\n{'='*60}\n  CONFIG_DB → IP addresses on {iface}\n{'='*60}")
    for k in cfg.scan_iter(f"INTERFACE|{iface}|*"):
        print(f"  {k}")

    print(f"\n{'='*60}\n  APPL_DB → Applied IPs on {iface}\n{'='*60}")
    for k in appl.scan_iter(f"INTF_TABLE:{iface}:*"):
        print(f"  {k}  →  {appl.hgetall(k)}")


def subscribe_live():
    r = connect(4)
    r.config_set("notify-keyspace-events", "KEA")
    pubsub = r.pubsub()
    pubsub.subscribe("__keyevent@4__:hset")
    print("\n[SUB] Watching CONFIG_DB for live changes … (Ctrl-C to stop)")
    try:
        for msg in pubsub.listen():
            if msg["type"] == "message":
                key = msg["data"]
                val = r.hgetall(key)
                print(f"\n  [CHANGE] {key}")
                for f, v in val.items():
                    print(f"    {f:<30} = {v}")
    except KeyboardInterrupt:
        print("\n[SUB] Stopped.")
    finally:
        pubsub.unsubscribe()
        pubsub.close()


def raw_lookup():
    print("DBs:", ", ".join(f"{k}={v}" for k,v in SONIC_DBS.items()))
    db_id = int(input("DB id > ").strip())
    key   = input("Key   > ").strip()
    r = connect(db_id)
    t = r.type(key)
    if   t == "hash":   print(pretty(r.hgetall(key)))
    elif t == "string": print(r.get(key))
    elif t == "list":   print(r.lrange(key, 0, -1))
    elif t == "set":    print(list(r.smembers(key)))
    elif t == "zset":   print(r.zrange(key, 0, -1, withscores=True))
    else:               print(f"Key not found or type={t}")


def list_all_keys():
    print("DBs:", ", ".join(f"{k}={v}" for k,v in SONIC_DBS.items()))
    db_id   = int(input("DB id   > ").strip())
    pattern = input("Pattern > (default *) ").strip() or "*"
    r = connect(db_id)
    keys = list_keys(r, pattern, count=500)
    for k in sorted(keys):
        print(" ", k)
    print(f"\n  Total: {len(keys)} keys")


# ─────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────
MENU = """
╔══════════════════════════════════════════════════════╗
║     SONiC Remote Redis Agent                         ║
║     PC → SSH Tunnel → 172.20.20.2 Redis              ║
╠══════════════════════════════════════════════════════╣
║  1  Dump CONFIG_DB  (ports / vlans / bgp)            ║
║  2  Dump APPL_DB    routes                           ║
║  3  Dump COUNTERS_DB port stats                      ║
║  4  Dump STATE_DB   port oper-state                  ║
║  5  Subscribe live CONFIG_DB changes                 ║
║  6  Raw key lookup  (any DB)                         ║
║  7  List all keys   (any DB)                         ║
║  8  Show ALL interfaces (admin / oper / IP)          ║
║  9  Inspect ONE interface in detail                  ║
║  q  Quit                                             ║
╚══════════════════════════════════════════════════════╝
"""

def main():
    # Start SSH tunnel automatically
    tunnel = SSHTunnel()
    tunnel.connect()
    tunnel.start()

    # Give tunnel a moment to be ready
    time.sleep(0.5)

    # Verify Redis connection
    try:
        connect(0).ping()
        print("[OK] Redis reachable through tunnel ✓\n")
    except Exception as e:
        print(f"[ERROR] Redis not reachable → {e}")
        tunnel.stop()
        sys.exit(1)

    print(MENU)
    try:
        while True:
            choice = input("Choice > ").strip().lower()
            if   choice == "1": dump_config_db()
            elif choice == "2": dump_appl_db_routes()
            elif choice == "3": dump_counters_db()
            elif choice == "4": dump_state_db()
            elif choice == "5": subscribe_live()
            elif choice == "6": raw_lookup()
            elif choice == "7": list_all_keys()
            elif choice == "8": dump_all_interfaces()
            elif choice == "9": inspect_one_interface()
            elif choice in ("q", "quit", "exit"):
                break
            else:
                print(MENU)
    except KeyboardInterrupt:
        pass
    finally:
        tunnel.stop()
        print("Bye.")

if __name__ == "__main__":
    main()