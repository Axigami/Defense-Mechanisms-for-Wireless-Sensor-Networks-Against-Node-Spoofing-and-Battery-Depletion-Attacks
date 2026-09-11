from flask import Flask, render_template, jsonify
import socket

app = Flask(__name__)

import os
CMD_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'attack.cmd')

def send_command(cmd):
    try:
        with open(CMD_FILE, 'w') as f:
            f.write(cmd + "\n")
        return True, "Command sent successfully via file bridge"
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    return render_template('attacker.html')

@app.route('/api/sybil/start', methods=['POST'])
def start_sybil():
    success, msg = send_command('START_SYBIL')
    if success:
        return jsonify({'status': 'success', 'message': 'Sybil Attack Started'})
    return jsonify({'status': 'error', 'message': f'Connection failed: {msg}'}), 500

@app.route('/api/sybil/stop', methods=['POST'])
def stop_sybil():
    success, msg = send_command('STOP_SYBIL')
    if success:
        return jsonify({'status': 'success', 'message': 'Sybil Attack Stopped'})
    return jsonify({'status': 'error', 'message': f'Connection failed: {msg}'}), 500

@app.route('/api/vna/start', methods=['POST'])
def start_vna():
    success, msg = send_command('START_VNA')
    if success:
        return jsonify({'status': 'success', 'message': 'VNA Attack Started'})
    return jsonify({'status': 'error', 'message': f'Command failed: {msg}'}), 500

@app.route('/api/vna/stop', methods=['POST'])
def stop_vna():
    success, msg = send_command('STOP_VNA')
    if success:
        return jsonify({'status': 'success', 'message': 'VNA Attack Stopped'})
    return jsonify({'status': 'error', 'message': f'Command failed: {msg}'}), 500

if __name__ == '__main__':
    print("Starting Attacker Dashboard on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001)
