#!/usr/bin/env python3
"""
Vampire Attack Controller Web Server
Provides web interface to trigger vampire attacks dynamically
Supports multi-node coordinated attacks
"""

from flask import Flask, render_template, jsonify, request
import os
import logging

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Command file path (relative to this script)
CMD_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'attack.cmd')

def send_command(cmd, nodes=None):
    """Write command to file bridge for Cooja to pick up
    
    Args:
        cmd: Command string
        nodes: List of node IDs (e.g., [29, 30]) or None for default node 29
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(CMD_FILE), exist_ok=True)
        
        # If nodes specified, append node list to command
        if nodes and isinstance(nodes, list):
            cmd_with_nodes = f"{cmd}|NODES={','.join(map(str, nodes))}"
        else:
            cmd_with_nodes = cmd
        
        with open(CMD_FILE, 'w') as f:
            f.write(cmd_with_nodes + "\n")
        
        logger.info(f"Command sent: {cmd_with_nodes}")
        return True, "Command sent successfully"
    except Exception as e:
        logger.error(f"Failed to send command: {e}")
        return False, str(e)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('attacker_vampire.html')

# ========================================
# CAROUSEL ATTACK ENDPOINTS
# ========================================
@app.route('/api/vampire/carousel/start', methods=['POST'])
def start_carousel():
    """Start carousel attack (version manipulation + DIO flooding)"""
    success, msg = send_command('START_CAROUSEL_ATTACK')
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Carousel Attack Started',
            'description': 'Node 29 is now performing version manipulation and DIO flooding'
        })
    return jsonify({'status': 'error', 'message': f'Failed: {msg}'}), 500

# ========================================
# STRETCH ATTACK ENDPOINTS
# ========================================
@app.route('/api/vampire/stretch/start', methods=['POST'])
def start_stretch():
    """Start stretch attack (rank manipulation)"""
    success, msg = send_command('START_STRETCH_ATTACK')
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Stretch Attack Started',
            'description': 'Node 29 is now advertising abnormally high rank (1500-2000)'
        })
    return jsonify({'status': 'error', 'message': f'Failed: {msg}'}), 500

# ========================================
# STEALTH ATTACK ENDPOINTS
# ========================================
@app.route('/api/vampire/stealth/start', methods=['POST'])
def start_stealth():
    """Start stealth attack (low-rate)"""
    data = request.get_json() or {}
    nodes = data.get('nodes', None)
    
    success, msg = send_command('START_STEALTH_ATTACK', nodes)
    if success:
        target = f"Nodes {nodes}" if nodes else "Node 29"
        return jsonify({
            'status': 'success',
            'message': 'Stealth Attack Started',
            'description': f'{target} performing subtle low-rate attack'
        })
    return jsonify({'status': 'error', 'message': f'Failed: {msg}'}), 500

# ========================================
# COORDINATED ATTACK ENDPOINT (NEW)
# ========================================
@app.route('/api/vampire/coordinated/start', methods=['POST'])
def start_coordinated():
    """Start coordinated multi-node attack"""
    data = request.get_json() or {}
    nodes = data.get('nodes', [29, 30, 31])  # Default to 3 nodes
    
    success, msg = send_command('START_COORDINATED_ATTACK', nodes)
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Coordinated Attack Started',
            'description': f'Nodes {nodes} executing synchronized attack phases'
        })
    return jsonify({'status': 'error', 'message': f'Failed: {msg}'}), 500

# ========================================
# STOP ATTACK ENDPOINT
# ========================================
@app.route('/api/vampire/stop', methods=['POST'])
def stop_attack():
    """Stop all vampire attacks"""
    data = request.get_json() or {}
    nodes = data.get('nodes', None)
    
    success, msg = send_command('STOP_ATTACK', nodes)
    if success:
        target = f"Nodes {nodes}" if nodes else "All nodes"
        return jsonify({
            'status': 'success',
            'message': 'All Attacks Stopped',
            'description': f'{target} returned to normal'
        })
    return jsonify({'status': 'error', 'message': f'Failed: {msg}'}), 500

# ========================================
# STATUS ENDPOINT
# ========================================
@app.route('/api/vampire/status', methods=['GET'])
def get_status():
    """Get current attack status"""
    # Check if command file exists
    cmd_exists = os.path.exists(CMD_FILE)
    
    # Check if log file exists (simulation running)
    log_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'run.log')
    sim_running = os.path.exists(log_file)
    
    return jsonify({
        'simulation_running': sim_running,
        'command_file_exists': cmd_exists,
        'cmd_file_path': CMD_FILE,
        'log_file_path': log_file
    })

if __name__ == '__main__':
    print("=" * 70)
    print("VAMPIRE ATTACK CONTROLLER")
    print("=" * 70)
    print()
    print("Starting web server on http://localhost:5002")
    print()
    print("Available endpoints:")
    print("  - http://localhost:5002/              (Main dashboard)")
    print("  - POST /api/vampire/carousel/start    (Carousel attack)")
    print("  - POST /api/vampire/stretch/start     (Stretch attack)")
    print("  - POST /api/vampire/stealth/start     (Stealth attack)")
    print("  - POST /api/vampire/coordinated/start (Coordinated multi-node)")
    print("  - POST /api/vampire/stop              (Stop all attacks)")
    print()
    print("Multi-node support:")
    print("  Send JSON body: {\"nodes\": [29, 30, 31]} to target specific nodes")
    print()
    print("Press CTRL+C to stop the server")
    print("=" * 70)
    print()
    
    app.run(host='0.0.0.0', port=5002, debug=False)
