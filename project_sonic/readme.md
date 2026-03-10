# SONiC Database Web Dashboard

A web-based dashboard for interacting with SONiC's internal Redis databases in real time. Runs on your PC and connects to SONiC via an automatic SSH tunnel — no manual setup required.

---

## Project Structure

```
project_sonic/
├── app.py            ← Flask backend (SSH tunnel + REST API)
├── index.html        ← Web dashboard frontend
├── README.md         ← This file
└── sonic_db_agent.py ← Optional CLI agent (runs on SONiC directly)
```

---

## Requirements

### Your PC
- Python 3.8+
- `sshpass` (optional but recommended for automatic tunnel)

### SONiC Switch
- SSH enabled
- Redis listening on TCP `127.0.0.1:6379`

---

## Installation

### 1. Install Python dependencies

```bash
pip install flask flask-cors redis paramiko
```

### 2. Install sshpass (recommended)

```bash
# Ubuntu / Debian
sudo apt install sshpass

# macOS
brew install hudochenkov/sshpass/sshpass
```

---

## SONiC Setup (one-time)

SSH into your SONiC instance and run these commands once:

```bash
# 1. Allow SSH password login
sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# 2. Set root password
passwd root
#set the password ex sonic123

# 3. Restart SSH
pkill sshd && /usr/sbin/sshd

# 4. Enable Redis TCP on localhost
redis-cli -s /run/redis/redis.sock config set bind "127.0.0.1"

# 5. Bring up management interface
ip link set eth0 up
```

### Make it permanent in ContainerLab topology

```yaml
name: project_sonic
topology:
  nodes:
    sonic1:
      kind: sonic-vs
      image: docker-sonic-vs:latest
      binds:
        - sonic_db_agent.py:/tmp/sonic_db_agent.py:ro
      exec:
        - ip link set eth0 up
        - sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
        - sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
        - echo 'root:sonic123' | chpasswd
        - pkill sshd || true
        - /usr/sbin/sshd
        - redis-cli -s /run/redis/redis.sock config set bind "127.0.0.1"
```

---

## Configuration

Edit the top of `app.py` to match your SONiC setup:

```python
SONIC_HOST     = "172.20.20.2"   # SONiC management IP
SONIC_SSH_PORT = 22               # SSH port
SONIC_USER     = "root"           # SSH username
SONIC_PASSWORD = "sonic123"       # SSH password
LOCAL_TUNNEL_PORT = 16379         # Local port for the tunnel (change if conflicts)
```

---

## Running

```bash
python3 app.py
```

Then open your browser at:

```
http://localhost:5000
```

The backend will:
1. Connect to SONiC via SSH automatically
2. Open a tunnel from `localhost:16379` → SONiC Redis
3. Serve the web dashboard

---

## Dashboard Pages

| Page | Description | Redis Source |
|---|---|---|
| **Overview** | Device info, port counts, route count | `CONFIG_DB` `DEVICE_METADATA\|localhost` |
| **Interfaces** | All interfaces with admin/oper/kernel state, IP, speed, MTU | `CONFIG_DB` + `APPL_DB` + `STATE_DB` |
| **Routes** | Full FIB route table with nexthops | `APPL_DB` `ROUTE_TABLE:*` |
| **Counters** | RX/TX bytes, errors, drops per port | `COUNTERS_DB` `COUNTERS:*` |
| **BGP** | BGP neighbor sessions and state | `CONFIG_DB` `BGP_NEIGHBOR\|*` |
| **VLANs** | VLAN cards with member ports, tagging mode, IPs | `CONFIG_DB` `VLAN\|*` `VLAN_MEMBER\|*` |
| **DB Explorer** | Browse any raw Redis key in any database | All DBs |
| **Live Feed** | Real-time Redis pub/sub event stream | Keyspace notifications |
| **Modify** | Write actions — interface, VLAN, BGP, raw key | `CONFIG_DB` write |

---

## Live Feed (Pub/Sub)

The Live Feed page subscribes to Redis keyspace notifications and shows every database change in real time.

**How to use:**
1. Click **▦ VLANs** → **◎ Live Feed** in the sidebar
2. Select which databases to watch (APPL_DB, CONFIG_DB, STATE_DB, etc.)
3. Click **▶ Start**
4. Run any config command on SONiC and watch events appear live

**Trigger events to test:**
```bash
# On SONiC — these will appear in the live feed
config interface ip add Ethernet0 192.168.1.1/24
config interface startup Ethernet0
config vlan add 100
```

---

## Modify Actions

The Modify page writes directly to Redis `CONFIG_DB` and triggers orchagent to apply changes.

| Section | Actions |
|---|---|
| **Interface** | Startup / Shutdown / Set MTU / Set Description / Add IP / Remove IP |
| **VLAN** | Add VLAN / Remove VLAN / Add Member / Remove Member |
| **BGP Neighbor** | Add / Remove / Startup / Shutdown |
| **Raw Key Write** | Write any field to any DB |

> **Note:** Changes written to `CONFIG_DB` are picked up by `orchagent` and propagated to `APPL_DB` and `ASIC_DB`. Watch the Live Feed to see the full propagation chain.

---

## SONiC Redis Database Map

| DB Name | ID | Contents |
|---|---|---|
| `APPL_DB` | 0 | Routes, neighbors, port tables pushed by orchagent |
| `ASIC_DB` | 1 | SAI objects written to the ASIC via syncd |
| `COUNTERS_DB` | 2 | Port/queue hardware statistics |
| `LOGLEVEL_DB` | 3 | Per-daemon log verbosity |
| `CONFIG_DB` | 4 | Running configuration (equivalent of config_db.json) |
| `PFC_WD_DB` | 5 | PFC Watchdog |
| `STATE_DB` | 6 | Operational state of all objects |
| `SNMP_OVERLAY_DB` | 7 | SNMP overlay |
| `ERROR_DB` | 8 | SAI API error logs from syncd |

---

## Troubleshooting

### Cannot connect to Redis
```bash
# Check Redis is listening on TCP inside SONiC
ss -tlnp | grep 6379
# Should show: 127.0.0.1:6379

# If not, enable it
redis-cli -s /run/redis/redis.sock config set bind "127.0.0.1"
```

### SSH connection refused
```bash
# Check SSH is running inside SONiC
ps aux | grep sshd

# Start it if not running
/usr/sbin/sshd

# Check password auth is enabled
grep PasswordAuthentication /etc/ssh/sshd_config
```

### Port 16379 already in use
```bash
# Kill whatever is using it
kill $(lsof -ti:16379)
# Then restart app.py
```

### Interface eth0 is DOWN (cannot SSH)
```bash
# Get inside the container first
sudo docker exec -it clab-project_sonic-sonic1 bash

# Bring up the management interface
ip link set eth0 up
```

---

## How It Works

```
Browser (http://localhost:5000)
        │
        │  HTTP / SSE requests
        ▼
   app.py  (Flask — runs on your PC)
        │
        │  SSH tunnel via paramiko / sshpass
        │  localhost:16379 → SONiC:127.0.0.1:6379
        ▼
   172.20.20.2  (SONiC switch)
        │
        ▼
   Redis  /run/redis/redis.sock
        │
        ├── APPL_DB   (DB 0)
        ├── ASIC_DB   (DB 1)
        ├── COUNTERS_DB (DB 2)
        ├── CONFIG_DB (DB 4)
        └── STATE_DB  (DB 6)
```

---

## Deliverables

- `app.py` — Flask backend with SSH tunnel, REST API, pub/sub SSE stream, and write actions
- `index.html` — Single-file web dashboard
- `sonic_db_agent.py` — CLI agent for running directly on the SONiC box
- `README.md` — This file