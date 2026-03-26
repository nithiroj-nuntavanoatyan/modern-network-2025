#!/usr/bin/env python3
"""
SONiC Web Dashboard - Backend
Flask server that opens SSH tunnel to SONiC and exposes Redis data as REST API.

Install: pip install flask flask-cors redis paramiko
Run:     python3 app.py
Open:    http://localhost:5000
"""

from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import redis
import json
import paramiko
import socket
import threading
import time
import os
import subprocess
import re

def natural_sort_key(s):
    """Sort Ethernet2 before Ethernet10 by splitting on digit boundaries."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split("([0-9]+)", s)]


app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
SONIC_HOST        = "192.168.4.5" #Don't forget to change this to your SONiC device's IP address
SONIC_SSH_PORT    = 22
SONIC_USER        = "admin"
SONIC_PASSWORD    = "YourPaSsWoRd"
LOCAL_TUNNEL_PORT = 16379

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
# SSH Tunnel
# ─────────────────────────────────────────────
class SSHTunnel:
    def __init__(self):
        self.proc      = None
        self.connected = False
        self._running  = False
        self._ssh      = None
        self._srv      = None

    def _kill_existing(self):
        os.system(f"fuser -k {LOCAL_TUNNEL_PORT}/tcp > /dev/null 2>&1")
        time.sleep(0.3)

    def connect(self):
        self._kill_existing()
        has_sshpass = os.system("which sshpass > /dev/null 2>&1") == 0
        if has_sshpass:
            return self._connect_sshpass()
        return self._connect_paramiko()

    def _connect_sshpass(self):
        cmd = [
            "sshpass", f"-p{SONIC_PASSWORD}",
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=10",
            "-N",
            "-L", f"{LOCAL_TUNNEL_PORT}:127.0.0.1:6379",
            f"{SONIC_USER}@{SONIC_HOST}",
            "-p", str(SONIC_SSH_PORT),
        ]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            get_redis(0).ping()
            self.connected = True
            print(f"[TUNNEL] Connected via sshpass -> 127.0.0.1:{LOCAL_TUNNEL_PORT}")
            return True
        except Exception as e:
            print(f"[TUNNEL] sshpass failed: {e}, trying paramiko...")
            return self._connect_paramiko()

    def _connect_paramiko(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=SONIC_HOST,
                port=SONIC_SSH_PORT,
                username=SONIC_USER,
                password=SONIC_PASSWORD,
                timeout=10,
            )
            self._ssh     = ssh
            self._running = True
            transport     = ssh.get_transport()
            transport.set_keepalive(10)

            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", LOCAL_TUNNEL_PORT))
            srv.listen(20)
            srv.settimeout(1)
            self._srv = srv

            def pump(src, dst):
                try:
                    while True:
                        data = src.recv(65536)
                        if not data:
                            break
                        dst.sendall(data)
                except Exception:
                    pass
                finally:
                    try:
                        src.close()
                    except Exception:
                        pass
                    try:
                        dst.close()
                    except Exception:
                        pass

            def handle(csock):
                try:
                    chan = transport.open_channel(
                        "direct-tcpip",
                        dest_addr=("localhost", 6379),
                        src_addr=csock.getpeername(),
                    )
                    t1 = threading.Thread(target=pump, args=(csock, chan), daemon=True)
                    t2 = threading.Thread(target=pump, args=(chan, csock), daemon=True)
                    t1.start()
                    t2.start()
                except Exception as e:
                    print(f"[TUNNEL] channel error: {e}")
                    csock.close()

            def accept_loop():
                while self._running:
                    try:
                        csock, _ = srv.accept()
                        threading.Thread(target=handle, args=(csock,), daemon=True).start()
                    except socket.timeout:
                        continue
                    except Exception:
                        break
                srv.close()

            threading.Thread(target=accept_loop, daemon=True).start()
            time.sleep(0.5)

            get_redis(0).ping()
            self.connected = True
            print(f"[TUNNEL] Connected via paramiko -> 127.0.0.1:{LOCAL_TUNNEL_PORT}")
            return True

        except Exception as e:
            print(f"[TUNNEL] Paramiko failed: {e}")
            self.connected = False
            return False

    def stop(self):
        self._running = False
        if self.proc:
            self.proc.terminate()
        if self._ssh:
            self._ssh.close()
        self._kill_existing()


tunnel = SSHTunnel()


def get_redis(db_id):
    return redis.Redis(
        host="127.0.0.1",
        port=LOCAL_TUNNEL_PORT,
        db=db_id,
        socket_connect_timeout=3,
        decode_responses=True,
    )


# ─────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/status")
def api_status():
    try:
        get_redis(0).ping()
        return jsonify({"connected": True, "host": SONIC_HOST, "tunnel_port": LOCAL_TUNNEL_PORT})
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)}), 503


@app.route("/api/connect", methods=["POST"])
def api_connect():
    data = request.json or {}
    global SONIC_HOST, SONIC_USER, SONIC_PASSWORD
    SONIC_HOST     = data.get("host",     SONIC_HOST)
    SONIC_USER     = data.get("username", SONIC_USER)
    SONIC_PASSWORD = data.get("password", SONIC_PASSWORD)
    tunnel.stop()
    time.sleep(0.5)
    if tunnel.connect():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Connection failed"}), 500


@app.route("/api/interfaces")
def api_interfaces():
    try:
        cfg  = get_redis(4)
        appl = get_redis(0)
        stat = get_redis(6)

        iface_map = {}

        for k in cfg.scan_iter("PORT|*"):
            iface_map[k.split("|", 1)[1]] = "port"
        for k in cfg.scan_iter("VLAN|*"):
            iface_map[k.split("|", 1)[1]] = "vlan"
        for k in cfg.scan_iter("LOOPBACK_INTERFACE|*"):
            name = k.split("|", 1)[1]
            if "|" not in name and ":" not in name:
                iface_map[name] = "loopback"
        for k in cfg.scan_iter("PORTCHANNEL|*"):
            iface_map[k.split("|", 1)[1]] = "portchannel"
        for k in appl.scan_iter("PORT_TABLE:*"):
            name = k.split(":", 1)[1]
            if name not in iface_map:
                if name.startswith("Bridge"):
                    t = "bridge"
                elif name.startswith("dummy"):
                    t = "dummy"
                elif name.startswith("eth"):
                    t = "mgmt"
                elif name.startswith("docker"):
                    t = "docker"
                elif name.startswith("lo"):
                    t = "loopback"
                else:
                    t = "other"
                iface_map[name] = t
        for k in stat.scan_iter("PORT_TABLE:*"):
            name = k.split(":", 1)[1]
            if name not in iface_map:
                iface_map[name] = "other"

        result = []
        for iface in sorted(iface_map.keys(), key=natural_sort_key):
            itype     = iface_map[iface]
            cfg_data  = (cfg.hgetall(f"PORT|{iface}") or
                         cfg.hgetall(f"VLAN|{iface}") or
                         cfg.hgetall(f"LOOPBACK_INTERFACE|{iface}") or
                         cfg.hgetall(f"PORTCHANNEL|{iface}") or {})
            appl_data = appl.hgetall(f"PORT_TABLE:{iface}") or {}
            stat_data = stat.hgetall(f"PORT_TABLE:{iface}") or {}

            ip_keys = (
                list(cfg.scan_iter(f"INTERFACE|{iface}|*")) +
                list(cfg.scan_iter(f"VLAN_INTERFACE|{iface}|*")) +
                list(cfg.scan_iter(f"LOOPBACK_INTERFACE|{iface}|*"))
            )
            appl_ip_keys = list(appl.scan_iter(f"INTF_TABLE:{iface}:*"))

            oper  = (stat_data.get("oper_status") or
                     appl_data.get("oper_status") or
                     appl_data.get("admin_status") or "—")
            admin = (cfg_data.get("admin_status") or
                     appl_data.get("admin_status") or "—")

            result.append({
                "name":        iface,
                "type":        itype,
                "admin":       admin,
                "oper":        oper,
                "speed":       stat_data.get("speed",  cfg_data.get("speed",  "—")),
                "mtu":         appl_data.get("mtu",    cfg_data.get("mtu",    "—")),
                "description": cfg_data.get("description", ""),
                "ips_config":  [k.split("|", 2)[2]  for k in ip_keys      if k.count("|") >= 2],
                "ips_applied": [k.split(":", 2)[2]   for k in appl_ip_keys if k.count(":") >= 2],
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kernel_interfaces")
def api_kernel_interfaces():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=SONIC_HOST,
            port=SONIC_SSH_PORT,
            username=SONIC_USER,
            password=SONIC_PASSWORD,
            timeout=10,
        )
        _, stdout, _ = ssh.exec_command("ip -br link show")
        lines = stdout.read().decode().strip().splitlines()
        ssh.close()

        result = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                name  = parts[0]
                state = parts[1]
                flags = parts[3] if len(parts) > 3 else ""
                result[name] = {
                    "kernel_state": state,
                    "flags": flags.strip("<>"),
                }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/routes")
def api_routes():
    try:
        r      = get_redis(0)
        keys   = list(r.scan_iter("ROUTE_TABLE:*", count=200))
        routes = []
        for k in sorted(keys)[:100]:
            val = r.hgetall(k)
            routes.append({
                "prefix":   k.split(":", 1)[1],
                "nexthop":  val.get("nexthop",  "?"),
                "ifname":   val.get("ifname",   "?"),
                "distance": val.get("distance", "?"),
            })
        return jsonify(routes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/counters")
def api_counters():
    try:
        r        = get_redis(2)
        name_map = r.hgetall("COUNTERS_PORT_NAME_MAP")
        result   = []
        for port, oid in sorted(name_map.items()):
            c = r.hgetall(f"COUNTERS:{oid}")
            result.append({
                "port":      port,
                "rx_bytes":  int(c.get("SAI_PORT_STAT_IF_IN_OCTETS",    0)),
                "tx_bytes":  int(c.get("SAI_PORT_STAT_IF_OUT_OCTETS",   0)),
                "rx_errors": int(c.get("SAI_PORT_STAT_IF_IN_ERRORS",    0)),
                "tx_errors": int(c.get("SAI_PORT_STAT_IF_OUT_ERRORS",   0)),
                "rx_drops":  int(c.get("SAI_PORT_STAT_IF_IN_DISCARDS",  0)),
                "tx_drops":  int(c.get("SAI_PORT_STAT_IF_OUT_DISCARDS", 0)),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bgp")
def api_bgp():
    try:
        cfg    = get_redis(4)
        stat   = get_redis(6)
        keys   = list(cfg.scan_iter("BGP_NEIGHBOR|*"))
        result = []
        for k in sorted(keys):
            peer     = k.split("|", 1)[1]
            cfg_data = cfg.hgetall(k)
            st_data  = stat.hgetall(f"BGP_NEIGHBOR_TABLE|{peer}")
            result.append({
                "peer":  peer,
                "asn":   cfg_data.get("asn",         "?"),
                "name":  cfg_data.get("name",         ""),
                "state": st_data.get("state",         "unknown"),
                "admin": cfg_data.get("admin_status", "?"),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/device")
def api_device():
    try:
        r    = get_redis(4)
        data = r.hgetall("DEVICE_METADATA|localhost")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/keys")
def api_keys():
    try:
        db_id   = int(request.args.get("db", 4))
        pattern = request.args.get("pattern", "*")
        r       = get_redis(db_id)
        keys    = list(r.scan_iter(pattern, count=200))[:200]
        return jsonify(sorted(keys))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/key")
def api_key():
    try:
        db_id = int(request.args.get("db", 4))
        key   = request.args.get("key", "")
        r     = get_redis(db_id)
        t     = r.type(key)
        if   t == "hash":   val = r.hgetall(key)
        elif t == "string": val = r.get(key)
        elif t == "list":   val = r.lrange(key, 0, -1)
        elif t == "set":    val = list(r.smembers(key))
        elif t == "zset":   val = r.zrange(key, 0, -1, withscores=True)
        else:               val = None
        return jsonify({"key": key, "type": t, "value": val})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# VLAN Database
# ─────────────────────────────────────────────

@app.route("/api/vlans")
def api_vlans():
    try:
        cfg  = get_redis(4)
        appl = get_redis(0)
        stat = get_redis(6)

        # Get all VLANs from CONFIG_DB
        vlan_keys = list(cfg.scan_iter("VLAN|*"))
        result    = []

        for vk in sorted(vlan_keys):
            vlan_name = vk.split("|", 1)[1]          # e.g. Vlan100
            vlan_id   = cfg.hgetall(vk).get("vlanid", vlan_name.replace("Vlan",""))
            vlan_cfg  = cfg.hgetall(vk)

            # Get VLAN interface IP if configured
            ip_keys  = list(cfg.scan_iter(f"VLAN_INTERFACE|{vlan_name}|*"))
            ips      = [k.split("|", 2)[2] for k in ip_keys if k.count("|") >= 2]

            # Get oper state from STATE_DB
            stat_data = stat.hgetall(f"VLAN_TABLE:{vlan_name}") or {}
            appl_data = appl.hgetall(f"VLAN_TABLE:{vlan_name}") or {}

            # Get members from CONFIG_DB VLAN_MEMBER
            member_keys = list(cfg.scan_iter(f"VLAN_MEMBER|{vlan_name}|*"))
            members = []
            for mk in sorted(member_keys):
                port     = mk.split("|", 2)[2]
                mem_data = cfg.hgetall(mk)
                # Get port oper state from STATE_DB
                port_stat = stat.hgetall(f"PORT_TABLE:{port}") or {}
                port_appl = appl.hgetall(f"PORT_TABLE:{port}") or {}
                members.append({
                    "port":         port,
                    "tagging_mode": mem_data.get("tagging_mode", "untagged"),
                    "oper":         port_stat.get("oper_status", port_appl.get("oper_status", "—")),
                    "speed":        port_stat.get("speed", "—"),
                })

            result.append({
                "name":        vlan_name,
                "vlan_id":     vlan_id,
                "description": vlan_cfg.get("description", ""),
                "oper":        stat_data.get("oper_status", appl_data.get("oper_status", "—")),
                "mtu":         vlan_cfg.get("mtu", appl_data.get("mtu", "—")),
                "ips":         ips,
                "members":     members,
                "member_count": len(members),
            })

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# Write / Modify Actions
# ─────────────────────────────────────────────

@app.route("/api/action/interface", methods=["POST"])
def action_interface():
    """Set interface admin_status or add/remove IP."""
    try:
        data   = request.json or {}
        iface  = data.get("name", "")
        action = data.get("action", "")
        cfg    = get_redis(4)

        if not iface:
            return jsonify({"ok": False, "error": "Missing interface name"}), 400

        if action == "startup":
            cfg.hset(f"PORT|{iface}", "admin_status", "up")
            return jsonify({"ok": True, "msg": f"{iface} admin_status set to up"})

        elif action == "shutdown":
            cfg.hset(f"PORT|{iface}", "admin_status", "down")
            return jsonify({"ok": True, "msg": f"{iface} admin_status set to down"})

        elif action == "set_mtu":
            mtu = data.get("mtu", "")
            if not mtu:
                return jsonify({"ok": False, "error": "Missing MTU value"}), 400
            cfg.hset(f"PORT|{iface}", "mtu", str(mtu))
            return jsonify({"ok": True, "msg": f"{iface} MTU set to {mtu}"})

        elif action == "set_description":
            desc = data.get("description", "")
            cfg.hset(f"PORT|{iface}", "description", desc)
            return jsonify({"ok": True, "msg": f"{iface} description set to '{desc}'"})

        elif action == "add_ip":
            ip = data.get("ip", "")
            if not ip:
                return jsonify({"ok": False, "error": "Missing IP address"}), 400
            cfg.hset(f"INTERFACE|{iface}|{ip}", "scope", "global")
            cfg.hset(f"INTERFACE|{iface}", "NULL", "NULL")
            return jsonify({"ok": True, "msg": f"IP {ip} added to {iface}"})

        elif action == "remove_ip":
            ip = data.get("ip", "")
            if not ip:
                return jsonify({"ok": False, "error": "Missing IP address"}), 400
            cfg.delete(f"INTERFACE|{iface}|{ip}")
            return jsonify({"ok": True, "msg": f"IP {ip} removed from {iface}"})

        else:
            return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/action/vlan", methods=["POST"])
def action_vlan():
    """Add or remove a VLAN."""
    try:
        data   = request.json or {}
        action = data.get("action", "")
        vlan   = data.get("vlan_id", "")
        cfg    = get_redis(4)

        if not vlan:
            return jsonify({"ok": False, "error": "Missing VLAN ID"}), 400

        if action == "add":
            cfg.hset(f"VLAN|Vlan{vlan}", "vlanid", str(vlan))
            return jsonify({"ok": True, "msg": f"VLAN {vlan} added"})

        elif action == "remove":
            cfg.delete(f"VLAN|Vlan{vlan}")
            return jsonify({"ok": True, "msg": f"VLAN {vlan} removed"})

        elif action == "add_member":
            member = data.get("member", "")
            mode   = data.get("mode", "untagged")
            if not member:
                return jsonify({"ok": False, "error": "Missing member port"}), 400
            cfg.hset(f"VLAN_MEMBER|Vlan{vlan}|{member}", "tagging_mode", mode)
            return jsonify({"ok": True, "msg": f"{member} added to VLAN {vlan} ({mode})"})

        elif action == "remove_member":
            member = data.get("member", "")
            if not member:
                return jsonify({"ok": False, "error": "Missing member port"}), 400
            cfg.delete(f"VLAN_MEMBER|Vlan{vlan}|{member}")
            return jsonify({"ok": True, "msg": f"{member} removed from VLAN {vlan}"})

        else:
            return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/action/bgp", methods=["POST"])
def action_bgp():
    """Add or remove BGP neighbor."""
    try:
        data   = request.json or {}
        action = data.get("action", "")
        peer   = data.get("peer", "")
        cfg    = get_redis(4)

        if not peer:
            return jsonify({"ok": False, "error": "Missing peer IP"}), 400

        if action == "add":
            asn  = data.get("asn", "")
            name = data.get("name", "")
            if not asn:
                return jsonify({"ok": False, "error": "Missing ASN"}), 400
            cfg.hset(f"BGP_NEIGHBOR|{peer}", mapping={
                "asn":          str(asn),
                "name":         name,
                "admin_status": "up",
            })
            return jsonify({"ok": True, "msg": f"BGP neighbor {peer} (ASN {asn}) added"})

        elif action == "shutdown":
            cfg.hset(f"BGP_NEIGHBOR|{peer}", "admin_status", "down")
            return jsonify({"ok": True, "msg": f"BGP neighbor {peer} shut down"})

        elif action == "startup":
            cfg.hset(f"BGP_NEIGHBOR|{peer}", "admin_status", "up")
            return jsonify({"ok": True, "msg": f"BGP neighbor {peer} started"})

        elif action == "remove":
            cfg.delete(f"BGP_NEIGHBOR|{peer}")
            return jsonify({"ok": True, "msg": f"BGP neighbor {peer} removed"})

        else:
            return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/action/raw", methods=["POST"])
def action_raw():
    """Write a raw key/field/value to any DB."""
    try:
        data  = request.json or {}
        db_id = int(data.get("db", 4))
        key   = data.get("key", "")
        field = data.get("field", "")
        value = data.get("value", "")
        if not key:
            return jsonify({"ok": False, "error": "Missing key"}), 400
        r = get_redis(db_id)
        if field:
            r.hset(key, field, value)
            return jsonify({"ok": True, "msg": f"SET {key} -> {field} = {value}"})
        else:
            r.set(key, value)
            return jsonify({"ok": True, "msg": f"SET {key} = {value}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# Pub/Sub  —  Server-Sent Events stream
# ─────────────────────────────────────────────
@app.route("/api/pubsub")
def api_pubsub():
    db_ids = request.args.getlist("db")
    db_ids = [int(d) for d in db_ids] if db_ids else [0, 1, 2, 4, 6]

    db_labels = {
        0: "APPL_DB",
        1: "ASIC_DB",
        2: "COUNTERS_DB",
        4: "CONFIG_DB",
        5: "PFC_WD_DB",
        6: "STATE_DB",
    }

    def sse(data):
        return "data: " + json.dumps(data) + "\n\n"

    def event_stream():
        # Enable keyspace notifications
        for db_id in db_ids:
            try:
                get_redis(db_id).config_set("notify-keyspace-events", "KEA")
            except Exception as e:
                yield sse({"type": "error", "msg": str(e)})

        try:
            r      = get_redis(0)
            pubsub = r.pubsub()

            channels = []
            for db_id in db_ids:
                channels += [
                    f"__keyevent@{db_id}__:hset",
                    f"__keyevent@{db_id}__:hdel",
                    f"__keyevent@{db_id}__:del",
                    f"__keyevent@{db_id}__:set",
                ]
            pubsub.subscribe(*channels)
            yield sse({"type": "connected", "dbs": db_ids, "msg": "Subscribed to DB events"})

            idle = 0
            while True:
                msg = pubsub.get_message(timeout=1.0)
                if msg is None:
                    idle += 1
                    if idle >= 15:
                        yield sse({"type": "heartbeat"})
                        idle = 0
                    continue

                idle = 0
                if msg["type"] not in ("message", "pmessage"):
                    continue

                channel = msg.get("channel", "")
                key     = msg.get("data", "")

                try:
                    ev_db_id = int(channel.split("@")[1].split("__")[0])
                except Exception:
                    ev_db_id = 0

                op = channel.split(":")[-1] if ":" in channel else "unknown"

                value = {}
                try:
                    rdb = get_redis(ev_db_id)
                    kt  = rdb.type(key)
                    if   kt == "hash":   value = rdb.hgetall(key)
                    elif kt == "string": value = {"value": rdb.get(key)}
                    elif kt == "list":   value = {"items": rdb.lrange(key, 0, -1)}
                    elif kt == "set":    value = {"members": list(rdb.smembers(key))}
                except Exception:
                    value = {}

                yield sse({
                    "type":    "event",
                    "db_id":   ev_db_id,
                    "db_name": db_labels.get(ev_db_id, f"DB{ev_db_id}"),
                    "op":      op,
                    "key":     key,
                    "value":   value,
                    "ts":      time.strftime("%H:%M:%S"),
                })

        except GeneratorExit:
            try:
                pubsub.unsubscribe()
                pubsub.close()
            except Exception:
                pass
        except Exception as e:
            yield sse({"type": "error", "msg": str(e)})

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ─────────────────────────────────────────────
# Start
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[START] Connecting to SONiC at {SONIC_HOST} ...")
    if tunnel.connect():
        print("[OK] Tunnel established")
    else:
        print("[WARN] Tunnel failed — use Configure button in web UI to reconnect")
    print("[START] Opening http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)