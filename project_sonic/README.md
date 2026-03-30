# SONiC Web Dashboard Backend

This repository contains a Flask backend for a SONiC web dashboard. The backend opens an SSH tunnel to a SONiC device, exposes Redis data through a REST API, and serves a static web UI from `index.html`.

## Features

- SSH tunnel to SONiC via `sshpass` or `paramiko`
- Local Redis access through forwarded port `16379`
- REST API for SONiC state, interfaces, routes, BGP, VLANs, counters, and more
- Action endpoints to modify SONiC config via Redis writes
- Pub/Sub endpoints for Redis event streaming and custom channel subscriptions
- Script API to execute YAML-defined playbooks against SONiC Redis

## Requirements

- Python 3
- Flask
- Flask-CORS
- redis
- paramiko
- PyYAML

Install dependencies with:

```bash
cd project_sonic
pip install -r requirements.txt
```

## Configuration

The application is configured in `project_sonic/app.py` using these variables:

- `SONIC_HOST` — SONiC device management IP, default `192.168.4.5`
- `SONIC_SSH_PORT` — SSH port, default `22`
- `SONIC_USER` — SSH username, default `admin`
- `SONIC_PASSWORD` — SSH password, default `YourPaSsWoRd`
- `LOCAL_TUNNEL_PORT` — local forwarded Redis port, default `16379`

Update these values before running the app, or call `/api/connect` with new credentials.

## Run

Start the backend from the `project_sonic` folder:

```bash
cd project_sonic
python3 app.py
```

Then open the frontend in your browser:

```text
http://localhost:5000
```

## API Endpoints

### Basic

- `GET /` — serve `index.html`
- `GET /api/status` — check Redis connectivity through the tunnel
- `POST /api/connect` — connect to SONiC with provided host/user/password

### SONiC Data

- `GET /api/interfaces` — list SONiC interfaces and status
- `GET /api/kernel_interfaces` — fetch kernel interface state from SONiC via SSH
- `GET /api/routes` — list routes from SONiC Redis
- `GET /api/counters` — port counters from `COUNTERS_DB`
- `GET /api/bgp` — BGP neighbor states
- `GET /api/device` — `DEVICE_METADATA|localhost` data
- `GET /api/keys` — list keys in a Redis DB
- `GET /api/key` — inspect one Redis key by type
- `GET /api/vlans` — list VLANs and memberships

### Write / Modify Actions

- `POST /api/action/interface`
  - `action`: `startup`, `shutdown`, `set_mtu`, `set_description`, `add_ip`, `remove_ip`
- `POST /api/action/vlan`
  - `action`: `add`, `remove`, `add_member`, `remove_member`
- `POST /api/action/bgp`
  - `action`: `add`, `shutdown`, `startup`, `remove`
- `POST /api/action/raw`
  - raw Redis write to any DB using `db`, `key`, `field`, `value`

### Pub/Sub

- `GET /api/pubsub` — SSE stream of Redis keyspace events for configured DBs
- `POST /api/pubsub/publish` — publish JSON messages to a Redis channel
- `GET /api/pubsub/subscribe` — SSE subscribe to custom Redis channels or patterns
- `GET /api/pubsub/channels` — list active Redis pub/sub channels

### Script Execution

- `GET /api/script/tasks` — list available script tasks
- `POST /api/script/run` — execute a YAML-based playbook against SONiC Redis

## Notes

- The backend prefers `sshpass` for tunnel creation if installed, otherwise it uses `paramiko`.
- This app reads/writes SONiC Redis directly, so use caution in production environments.
- The frontend is served from static files in the same `project_sonic` folder.

## Helpful commands

```bash
cd project_sonic
python3 app.py
```

If you want to update SONiC credentials from the API:

```bash
curl -X POST http://localhost:5000/api/connect \
  -H 'Content-Type: application/json' \
  -d '{"host": "192.168.4.5", "username": "admin", "password": "YourPaSsWoRd"}'
```
