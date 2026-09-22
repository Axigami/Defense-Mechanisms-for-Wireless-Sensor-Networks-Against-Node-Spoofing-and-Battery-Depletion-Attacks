#!/usr/bin/env python3
"""
WSN Real-time Monitoring Server
Nhận dữ liệu từ Sink qua CoAP và serve dashboard qua HTTP
"""

import asyncio
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'defense')))
from defense import DefenseSystem
defense_sys = DefenseSystem()
import logging
import time
from datetime import datetime
from collections import deque
from flask import Flask, render_template, jsonify, send_from_directory
from flask_cors import CORS
import aiocoap
import aiocoap.resource as resource
import threading
import re


import random

simulated_rssi_baselines = {}

def get_realistic_rssi(node_id):
    if node_id >= 100:
        # Kẻ tấn công tạo hàng loạt Sybil ID từ cùng 1 ăng ten (cùng RSSI)
        if 'attacker' not in simulated_rssi_baselines:
            simulated_rssi_baselines['attacker'] = random.uniform(-65, -45)
        base = simulated_rssi_baselines['attacker']
    else:
        # Node Legit có vị trí vật lý riêng biệt
        if node_id not in simulated_rssi_baselines:
            simulated_rssi_baselines[node_id] = random.uniform(-85, -45)
        base = simulated_rssi_baselines[node_id]
        
    # Bơm nhiễu chuẩn Gaussian (Jitter)
    noise = random.gauss(0, 1.0)
    return round(base + noise, 1)


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Flask app
app = Flask(__name__)
CORS(app)

# Global data storage
network_data = {
    'timestamp': None,
    'sink_id': None,
    'version': None,
    'active_routes': 0,
    'total_packets_received': 0,
    'total_packets_sent': 0,
    'nodes': {},  # {node_id: {cluster, seq, energy, temp, latency, last_seen}}
    'history': deque(maxlen=1000),  # Lưu lịch sử để vẽ charts
    'fire_alerts': {}, # {node_id: timestamp}
    'vna_events': deque(maxlen=50),
    'sybil_events': set(), # {timestamp, node_id, old_version, new_version}
    'cluster_stats': {
        1: {'energy_sum': 0, 'node_count': 0, 'parent_switches': 0},
        2: {'energy_sum': 0, 'node_count': 0, 'parent_switches': 0}
    }
}

# Parse Cooja log format
LOG_PATTERNS = {
    'rx': re.compile(r'RX sink=(?P<sink>\d+) cluster=(?P<cl>\d+) node=(?P<node>\d+) '
                     r'seq=(?P<seq>\d+) energy_mj=(?P<e>\d+) temp_c=(?P<temp_int>\d+)\.(?P<temp_dec>\d+) '
                     r'bytes=\d+ latency_ms=(?P<lat>\d+)'),
    'tx': re.compile(r'(TX cluster=|TXFAIL|NORMAL_TX|ATTACK_TX)'),
    'dead': re.compile(r'DEAD cluster=(?P<cl>\d+) node=(?P<node>\d+) time_alive_s=(?P<alive>\d+)'),
    'sink_start': re.compile(r'SINK_START sink=(?P<sink>\d+) version=(?P<ver>\d+_\d+)'),
    'version': re.compile(r'VERSION_UPDATE sink=(?P<sink>\d+) old_version=(?P<old>\d+_\d+) '
                          r'new_version=(?P<new>\d+_\d+)'),
    'health': re.compile(r'HEALTH sink=(?P<sink>\d+) active_routes=(?P<routes>\d+) '
                         r'version=(?P<ver>\d+_\d+)'),
    'vna': re.compile(r'ID:(?P<node>\d+).*ATTACK_VNA.*: Triggered! Version changed (?P<old>\d+) -> (?P<new>\d+)'),
    'parent_switch': re.compile(r'ID:(?P<node>\d+).*parent switch:'),
    'status': re.compile(r'STATUS node=(?P<node>\d+) energy_mj=(?P<e>\d+)'),
}


class CoAPDataResource(resource.Resource):
    """CoAP resource để nhận dữ liệu từ Sink"""
    
    async def render_post(self, request):
        """Xử lý POST request từ Sink"""
        try:
            payload = request.payload.decode('utf-8')
            logger.info(f"CoAP POST received: {payload[:200]}...")
            
            # Parse log line
            await self.parse_log_data(payload)
            
            return aiocoap.Message(code=aiocoap.CHANGED, payload=b'OK')
        
        except Exception as e:
            logger.error(f"Error processing CoAP request: {e}")
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=str(e).encode())
    
    async def parse_log_data(self, log_text):
        """Parse log text và cập nhật network_data"""
        global network_data
        
        lines = log_text.split('\n')
        timestamp = datetime.now().timestamp()
        
        for line in lines:
            # Parse RX messages (packet received at sink)
            m = LOG_PATTERNS['rx'].search(line)
            if m:
                node_id = int(m.group('node'))
                cluster = int(m.group('cl'))
                seq = int(m.group('seq'))
                energy = int(m.group('e'))
                temp = float(f"{m.group('temp_int')}.{m.group('temp_dec')}")
                latency = int(m.group('lat'))
                
                # Cập nhật node data
                if node_id not in network_data['nodes']:
                    network_data['nodes'][node_id] = {
                        'cluster': cluster,
                        'seq': seq,
                        'energy_mj': energy,
                        'temp_c': temp,
                        'latency_ms': latency,
                        'last_seen': timestamp,
                        'packets_received': 1,
                    }
                else:
                    network_data['nodes'][node_id].update({
                        'seq': seq,
                        'energy_mj': energy,
                        'temp_c': temp,
                        'latency_ms': latency,
                        'last_seen': timestamp,
                        'packets_received': network_data['nodes'][node_id].get('packets_received', 0) + 1,
                        'is_alive': True,  # Receiving data means node is alive
                    })
                
                if temp > 60.0:
                    network_data['fire_alerts'][node_id] = timestamp
                elif node_id in network_data['fire_alerts']:
                    del network_data['fire_alerts'][node_id]
                
                if node_id >= 100:
                    if 'sybil_events' not in network_data:
                        network_data['sybil_events'] = set()
                    network_data['sybil_events'].add(node_id)
                
                network_data['total_packets_received'] += 1
                
                # Add to history
                network_data['history'].append({
                    'timestamp': timestamp,
                    'node_id': node_id,
                    'energy_mj': energy,
                    'temp_c': temp,
                    'latency_ms': latency,
                })
                
                logger.info(f"Updated node {node_id}: energy={energy}mJ, temp={temp}°C, latency={latency}ms")
            
            # Parse TX messages (packet sent from node)
            m = LOG_PATTERNS['tx'].search(line)
            if m:
                network_data['total_packets_sent'] += 1
            
            # Parse VERSION_UPDATE
            m = LOG_PATTERNS['version'].search(line)
            if m:
                network_data['version'] = m.group('new')
                network_data['sink_id'] = int(m.group('sink'))
                logger.info(f"Version updated to: {network_data['version']}")
            
            # Parse HEALTH
            m = LOG_PATTERNS['health'].search(line)
            if m:
                network_data['active_routes'] = int(m.group('routes'))
                network_data['version'] = m.group('ver')
                network_data['sink_id'] = int(m.group('sink'))
            
            # Parse STATUS
        m = LOG_PATTERNS['status'].search(line)
        if m:
            node_id = int(m.group('node'))
            energy = int(m.group('e'))
            if node_id in network_data['nodes']:
                network_data['nodes'][node_id]['energy_mj'] = energy
                network_data['nodes'][node_id]['last_seen'] = timestamp

        # Parse DEAD messages
            m = LOG_PATTERNS['dead'].search(line)
            if m:
                node_id = int(m.group('node'))
                if node_id in network_data['nodes']:
                    network_data['nodes'][node_id]['is_alive'] = False
                    network_data['nodes'][node_id]['energy_mj'] = 0
                    logger.info(f"Node {node_id} DEAD")
            
            # Parse SINK_START messages
            m = LOG_PATTERNS['sink_start'].search(line)
            if m:
                network_data['version'] = m.group('ver')
                network_data['sink_id'] = int(m.group('sink'))
                logger.info(f"Sink {network_data['sink_id']} started with version {network_data['version']}")
        
        network_data['timestamp'] = timestamp


class LogFileWatcher(threading.Thread):
    """Thread để theo dõi log file và tự động cập nhật"""
    
    def __init__(self, log_file_path):
        super().__init__(daemon=True)
        self.log_file_path = log_file_path
        self.running = True
    
    def run(self):
        """Doc log file va parse real-time, ho tro log rotation"""
        import time
        import glob
        import os
        
        while self.running:
            logger.info(f"Watching log file: {self.log_file_path}")
            try:
                with open(self.log_file_path, 'r') as f:
                    logger.info("Reading existing log data...")
                    line_count = 0
                    for line in f:
                        self.process_line(line)
                        line_count += 1
                    
                    logger.info(f"Processed {line_count} existing log lines")
                    
                    last_report = time.time()
                    lines_parsed = 0
                    while self.running:
                        line = f.readline()
                        if line:
                            self.process_line(line)
                            lines_parsed += 1
                        else:
                            # Check for new log file (log rotation)
                            try:
                                log_dir = os.path.dirname(self.log_file_path)
                                all_logs = glob.glob(os.path.join(log_dir, 'run_*.log'))
                                if all_logs:
                                    latest_file = max(all_logs, key=os.path.getctime)
                                    if latest_file != self.log_file_path:
                                        logger.info(f"Log rotated! Switching to new file: {latest_file}")
                                        self.log_file_path = latest_file
                                        break # Break to reopen new file
                            except Exception:
                                pass
                            threading.Event().wait(1)
                            
                        if time.time() - last_report > 10:
                            if lines_parsed > 0:
                                logger.info(f"Parsed {lines_parsed} log lines in the last 10 seconds.")
                                lines_parsed = 0
                            last_report = time.time()
            except FileNotFoundError:
                logger.error(f"Log file not found: {self.log_file_path}")
                threading.Event().wait(2)
            except Exception as e:
                logger.error(f"Error watching log file: {e}")
                threading.Event().wait(2)
    
    def process_line(self, line):
        """Process một dòng log"""
        global network_data
        timestamp = datetime.now().timestamp()
        
        # Parse RX
        m = LOG_PATTERNS['rx'].search(line)
        if m:
            node_id = int(m.group('node'))
            cluster = int(m.group('cl'))
            seq = int(m.group('seq'))
            energy = int(m.group('e'))
            temp = float(f"{m.group('temp_int')}.{m.group('temp_dec')}")
            # Parse và validate latency (cap tại 10000ms để tránh giá trị lỗi)
            latency_raw = int(m.group('lat'))
            latency = min(latency_raw, 10000)  # Max 10 giây
            rssi = get_realistic_rssi(node_id)
            
            if latency_raw > 10000:
                logger.warning(f"Abnormal latency detected: {latency_raw}ms (capped to 10000ms)")
            
            # 1. ALWAYS REGISTER NODE TO DASHBOARD FIRST (kể cả giả mạo)
            if node_id not in network_data['nodes']:
                network_data['nodes'][node_id] = {
                    'cluster': cluster,
                    'seq': seq,
                    'energy_mj': energy,
                    'temp_c': temp,
                    'latency_ms': latency,
                    'last_seen': timestamp,
                    'packets_received': 1,
                    'is_alive': True,
                }
                logger.info(f"New node detected: {node_id}")
            
            # 2. RUN DEFENSE SYSTEM
            passed = defense_sys.process_packet(node_id, rssi, temp)
            network_data['defense_data'] = defense_sys.get_ui_data()
            
            if not passed:
                return # DROP PACKET - Ngừng cập nhật trạng thái
                
            # 3. IF PASSED, UPDATE NODE STATS
            network_data['nodes'][node_id].update({
                'seq': seq,
                'energy_mj': energy,
                'temp_c': temp,
                'latency_ms': latency,
                'last_seen': timestamp,
                'packets_received': network_data['nodes'][node_id].get('packets_received', 0) + 1,
            })
            
            if temp > 60.0:
                network_data['fire_alerts'][node_id] = timestamp
            elif node_id in network_data['fire_alerts']:
                del network_data['fire_alerts'][node_id]
                
            if node_id >= 100:
                if 'sybil_events' not in network_data:
                    network_data['sybil_events'] = set()
                network_data['sybil_events'].add(node_id)
            
            network_data['total_packets_received'] += 1
            network_data['history'].append({
                'timestamp': timestamp,
                'node_id': node_id,
                'energy_mj': energy,
                'temp_c': temp,
                'latency_ms': latency,
            })
            
            # Log mỗi 10 packets
            if network_data['total_packets_received'] % 10 == 0:
                logger.info(f"Processed {network_data['total_packets_received']} packets, {len(network_data['nodes'])} nodes")
            return  # Found match, exit
        
        # Parse VNA Attack
        m = LOG_PATTERNS['vna'].search(line)
        if m:
            node_id = int(m.group('node'))
            network_data['vna_events'].append({
                'timestamp': timestamp,
                'node_id': node_id,
                'old_version': m.group('old'),
                'new_version': m.group('new')
            })
            logger.warning(f"VNA ATTACK DETECTED from node {node_id}")
            return
            
        # Parse Parent Switch
        m = LOG_PATTERNS['parent_switch'].search(line)
        if m:
            node_id = int(m.group('node'))
            if node_id in network_data['nodes']:
                cluster = network_data['nodes'][node_id]['cluster']
                if cluster in network_data['cluster_stats']:
                    network_data['cluster_stats'][cluster]['parent_switches'] += 1
            return
        
        # Parse STATUS
        m = LOG_PATTERNS['status'].search(line)
        if m:
            node_id = int(m.group('node'))
            energy = int(m.group('e'))
            if node_id in network_data['nodes']:
                network_data['nodes'][node_id]['energy_mj'] = energy
                network_data['nodes'][node_id]['last_seen'] = timestamp

        # Parse DEAD messages (node ran out of energy)
        m = LOG_PATTERNS['dead'].search(line)
        if m:
            node_id = int(m.group('node'))
            cluster = int(m.group('cl'))
            time_alive = int(m.group('alive'))
            
            if node_id in network_data['nodes']:
                network_data['nodes'][node_id]['is_alive'] = False
                network_data['nodes'][node_id]['energy_mj'] = 0
                logger.info(f"Node {node_id} DEAD (cluster={cluster}, alive={time_alive}s)")
            return
        
        # Parse SINK_START messages
        m = LOG_PATTERNS['sink_start'].search(line)
        if m:
            network_data['version'] = m.group('ver')
            network_data['sink_id'] = int(m.group('sink'))
            logger.info(f"Sink {network_data['sink_id']} started with version {network_data['version']}")
            return
        
        # Parse TX
        m = LOG_PATTERNS['tx'].search(line)
        if m:
            network_data['total_packets_sent'] += 1
            return
        
        # Parse VERSION_UPDATE
        m = LOG_PATTERNS['version'].search(line)
        if m:
            network_data['version'] = m.group('new')
            network_data['sink_id'] = int(m.group('sink'))
            logger.info(f"Version updated to: {network_data['version']}")
            return
        
        # Parse HEALTH
        m = LOG_PATTERNS['health'].search(line)
        if m:
            network_data['active_routes'] = int(m.group('routes'))
            network_data['version'] = m.group('ver')
            network_data['sink_id'] = int(m.group('sink'))
            return
    
    def stop(self):
        self.running = False


# ============ Flask Routes ============


# ==========================================
# VIRTUAL NODE SIMULATION API
# ==========================================
def fake_node_loop(node_id):
    # Determine base RSSI for legit node (random)
    rssi_base = random.uniform(-85, -45)
    simulated_rssi_baselines[node_id] = rssi_base
    
    seq = 0
    energy = 30000
    
    while True:
        # Check if node was blacklisted
        defense_data = defense_sys.get_ui_data()
        if node_id in defense_data.get('trust_db', {}):
            if defense_data['trust_db'][node_id].get('blacklisted', False):
                logger.info(f"Fake Node {node_id} was blacklisted. Stopping simulation.")
                break
                
        time.sleep(2.0)
        seq += 1
        energy -= random.randint(10, 50)
        if energy <= 0:
            break
            
        temp = round(random.uniform(25.0, 30.0), 1)
        rssi = round(rssi_base + random.gauss(0, 1.0), 1)
        
        passed = defense_sys.process_packet(node_id, rssi, temp)
        timestamp = datetime.now().timestamp()
        
        if node_id not in network_data['nodes']:
            network_data['nodes'][node_id] = {
                'cluster': 1,
                'seq': seq,
                'energy_mj': energy,
                'temp_c': temp,
                'latency_ms': 50,
                'packets_received': 1,
                'is_alive': True,
                'last_seen': timestamp
            }
        else:
            network_data['nodes'][node_id].update({
                'seq': seq,
                'energy_mj': energy,
                'temp_c': temp,
                'latency_ms': 50,
                'packets_received': network_data['nodes'][node_id].get('packets_received', 0) + 1,
                'is_alive': True,
                'last_seen': timestamp
            })
            
        network_data['total_packets_received'] += 1
        network_data['history'].append({
            'timestamp': timestamp,
            'node_id': node_id,
            'energy_mj': energy,
            'temp_c': temp,
            'rssi': rssi
        })

from flask import request

@app.route('/api/spawn_node', methods=['POST'])
def spawn_node():
    node_id = random.randint(500, 999) # Spawn legit node with ID 500-999
    threading.Thread(target=fake_node_loop, args=(node_id,), daemon=True).start()
    logger.info(f"SPAWNED Virtual Legit Node {node_id}")
    return jsonify({"status": "success", "node_id": node_id})

@app.route('/')
def index():
    """Serve dashboard"""
    return render_template('dashboard.html')

@app.route('/api/network')
def get_network_data():
    """API để lấy dữ liệu network"""
    current_time = datetime.now().timestamp()
    
    # Xóa các cảnh báo cháy cũ (quá 15 giây không nhận được tín hiệu)
    if 'fire_alerts' in network_data:
        stale_alerts = [n for n, t in network_data['fire_alerts'].items() if current_time - t > 15]
        for n in stale_alerts:
            del network_data['fire_alerts'][n]

    # Đếm số node còn sống (is_alive=True)
    defense_data = defense_sys.get_ui_data()
    blacklisted_nodes = {int(k) for k, v in defense_data.get('trust_db', {}).items() if v.get('blacklisted', False)}
    active_nodes_count = sum(1 for node_id, node in network_data['nodes'].items() if node.get('is_alive', True) and node_id not in blacklisted_nodes)
    
    # Tách dữ liệu energy theo cluster
    c1_nodes = [n for n in network_data['nodes'].values() if n.get('is_alive', True) and n['cluster'] == 1]
    c2_nodes = [n for n in network_data['nodes'].values() if n.get('is_alive', True) and n['cluster'] == 2]
    
    avg_energy_c1 = sum(n['energy_mj'] for n in c1_nodes) / len(c1_nodes) if c1_nodes else 0
    avg_energy_c2 = sum(n['energy_mj'] for n in c2_nodes) / len(c2_nodes) if c2_nodes else 0
    
    return jsonify({
        'timestamp': network_data['timestamp'],
        'sink_id': network_data['sink_id'],
        'version': network_data['version'],
        'active_routes': network_data['active_routes'],
        'total_packets_received': network_data['total_packets_received'],
        'total_packets_sent': network_data['total_packets_sent'],
        'fire_alerts': list(network_data.get('fire_alerts', {}).keys()),
        'active_nodes': active_nodes_count,  # Số node còn sống
        'total_nodes': len(network_data['nodes']),  # Tổng số node đã thấy
        'pdr': (network_data['total_packets_received'] / network_data['total_packets_sent'] * 100) 
               if network_data['total_packets_sent'] > 0 else 0,
        'cluster_stats': {
            1: {'avg_energy': avg_energy_c1, 'parent_switches': network_data['cluster_stats'][1]['parent_switches']},
            2: {'avg_energy': avg_energy_c2, 'parent_switches': network_data['cluster_stats'][2]['parent_switches']}
        },
        'vna_events': list(network_data['vna_events']),
        'defense_data': network_data.get('defense_data', {'is_armed': False, 'logs': [], 'trust_db': {}}),
        'sybil_events': list(network_data.get('sybil_events', set())),
        'nodes': [
            {
                'node_id': node_id,
                **node_data
            }
            for node_id, node_data in network_data['nodes'].items()
        ]
    })

@app.route('/api/history')
def get_history():
    """API để lấy lịch sử dữ liệu"""
    return jsonify(list(network_data['history']))

@app.route('/api/stats')
def get_stats():
    """API để lấy thống kê tổng quan"""
    nodes = network_data['nodes']
    
    if not nodes:
        return jsonify({
            'total_nodes': 0,
            'avg_energy': 0,
            'avg_temp': 0,
            'avg_latency': 0,
            'nodes_alive': 0,
        })
    
    # Chỉ tính average cho node còn sống
    alive_nodes = [n for n in nodes.values() if n.get('is_alive', True)]
    
    return jsonify({
        'total_nodes': len(nodes),
        'avg_energy': sum(n['energy_mj'] for n in alive_nodes) / len(alive_nodes) if alive_nodes else 0,
        'avg_temp': sum(n['temp_c'] for n in alive_nodes) / len(alive_nodes) if alive_nodes else 0,
        'avg_latency': sum(n['latency_ms'] for n in alive_nodes) / len(alive_nodes) if alive_nodes else 0,
        'nodes_alive': len(alive_nodes),
    })


# ============ CoAP Server ============

async def run_coap_server():
    """Chạy CoAP server"""
    root = resource.Site()
    root.add_resource(['data'], CoAPDataResource())
    
    # Note: aiocoap on Windows requires specific interface, not 0.0.0.0
    # Use localhost (::1 for IPv6) or specific interface address
    try:
        await aiocoap.Context.create_server_context(root, bind=('::1', 5683))
        logger.info("CoAP server started on coap://[::1]:5683/data")
    except Exception as e:
        logger.warning(f"Could not bind CoAP to IPv6, trying IPv4: {e}")
        try:
            await aiocoap.Context.create_server_context(root, bind=('127.0.0.1', 5683))
            logger.info("CoAP server started on coap://127.0.0.1:5683/data")
        except Exception as e2:
            logger.error(f"Could not start CoAP server: {e2}")
            logger.info("Continuing without CoAP (log file mode only)")
            return
    
    # Keep running
    await asyncio.get_running_loop().create_future()


def start_coap_server():
    """Start CoAP server in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_coap_server())


# ============ Main ============

if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    logger.info("=" * 60)
    logger.info("WSN Real-time Monitoring Server")
    logger.info("=" * 60)
    
    # Check for log file argument
    log_files_to_watch = []
    
    if len(sys.argv) > 1:
        log_path = Path(sys.argv[1])
        log_dir = log_path.parent
        
        # Tìm tất cả log files (run.log, run2.log, run3.log...)
        if log_dir.exists():
            import os
            import glob
            all_logs = glob.glob(os.path.join(log_dir, 'run_*.log'))
            # Cung kiem tra file run.log cu neu co
            all_logs.extend(glob.glob(os.path.join(log_dir, 'run.log')))
            if all_logs:
                logger.info(f"Found {len(all_logs)} log files in {log_dir}")
                latest_log = max(all_logs, key=os.path.getctime)
            else:
                logger.warning(f"No log files found in {log_dir}. Defaulting to run_1.log")
                latest_log = os.path.join(log_dir, 'run_1.log')
                
            logger.info(f"Starting watcher on: {os.path.basename(latest_log)}")
            watcher = LogFileWatcher(latest_log)
            watcher.start()
            log_files_to_watch.append(latest_log)
        else:
            logger.warning(f"Log directory not found: {log_dir}")
    else:
        logger.info("No log file specified. Server will run in API-only mode")
        logger.info("Usage: python monitor_server.py [path_to_log_file]")
    
    # Start CoAP server in separate thread (optional - may fail on Windows)
    logger.info("Attempting to start CoAP server...")
    coap_thread = threading.Thread(target=start_coap_server, daemon=True)
    coap_thread.start()
    time.sleep(1)  # Give CoAP time to start or fail
    
    logger.info("Starting Flask web server...")
    logger.info("Dashboard: http://localhost:5000")
    logger.info("API: http://localhost:5000/api/network")
    logger.info("=" * 60)
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

