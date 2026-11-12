#!/usr/bin/env python3
"""
ML Defense Monitor Server
=========================
Dedicated monitoring dashboard for ML-based vampire attack detection.

Architecture:
  1. Parses structured ML_ALERT log lines from Contiki-NG node serial output
  2. Presents alerts on a web dashboard for human supervisor review
  3. ACL auto-approve engine handles clear-cut detections automatically
  4. Approved blocks are written to block.cmd for the simulation to pick up

Ports:
  - HTTP Dashboard: 5003 (configurable)
"""

import asyncio
import json
import logging
import time
import os
import re
import threading
import glob
from datetime import datetime
from collections import deque, defaultdict
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Flask app
app = Flask(__name__)
CORS(app)

# ============================================================
# ACL AUTO-APPROVE CONFIGURATION
# These thresholds define when the ACL engine auto-approves
# a block without human intervention
# ============================================================
ACL_CONFIG = {
    'auto_approve_consecutive_alerts': 4,     # Auto-approve if >= 4 consecutive alerts
    'auto_approve_dio_rate': 50,              # Auto-approve if DIO rate >= 50
    'auto_approve_rank_delta': 500,           # Auto-approve if rank delta >= 500
    'auto_approve_version_delta': 5,          # Auto-approve if version delta >= 5
    'alert_expiry_seconds': 300,              # Alerts expire after 5 minutes
    'block_duration_seconds': 600,            # Blocks last 10 minutes by default
}

# Whitelist of trusted nodes (Sink 1, Sink 2, Root) that can NEVER be blocked
TRUSTED_ADDR_PATTERNS = [
    re.compile(r'.*::1$', re.IGNORECASE),
    re.compile(r'.*::2$', re.IGNORECASE),
    re.compile(r'.*:0001$', re.IGNORECASE),
    re.compile(r'.*:0002$', re.IGNORECASE),
    re.compile(r'.*::01$', re.IGNORECASE),
    re.compile(r'.*::02$', re.IGNORECASE),
]

def is_trusted_suspect(suspect_addr):
    addr = suspect_addr.strip().lower()
    for pattern in TRUSTED_ADDR_PATTERNS:
        if pattern.match(addr):
            return True
    return False

# ============================================================
# GLOBAL DATA STORES
# ============================================================

# All ML alerts received (most recent first)
ml_alerts = deque(maxlen=500)

# Pending alerts awaiting human review (not yet auto-approved)
pending_alerts = {}  # key: suspect_addr -> alert_data

# Approved blocks (confirmed by human or ACL engine)
approved_blocks = {}  # key: suspect_addr -> block_info

# Rejected alerts (supervisor decided not to block)
rejected_alerts = {}  # key: suspect_addr -> reject_info

# Auto-approved by ACL (for auditing)
auto_approved = deque(maxlen=100)

# Alert aggregation per suspect
suspect_profiles = defaultdict(lambda: {
    'first_seen': None,
    'last_seen': None,
    'total_alerts': 0,
    'alert_sources': defaultdict(int),  # ML vs HEURISTIC counts
    'attack_types': defaultdict(int),   # CAROUSEL, STRETCH etc counts
    'reporting_nodes': set(),            # Which detector nodes reported
    'max_dio_rate': 0,
    'max_rank_delta': 0,
    'max_version_delta': 0,
    'max_consecutive': 0,
    'latest_features': {},
    'status': 'pending',  # pending, blocked, rejected, expired
})

# Stats
stats = {
    'total_alerts': 0,
    'total_auto_approved': 0,
    'total_manual_approved': 0,
    'total_rejected': 0,
    'total_expired': 0,
}

# Block command file path
BLOCK_CMD_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'block.cmd')

# ============================================================
# LOG PARSER
# ============================================================

# Parse ML_ALERT structured log lines emitted by vampire_defense_ml.c
# Format: ML_ALERT detector=<ID> suspect=<ADDR> type=<TYPE> source=<SRC>
#         alerts=<N> dio_rate=<V> version_delta=<V> rank=<V>
#         rank_delta=<V> is_poison=<V>
ML_ALERT_PATTERN = re.compile(
    r'ML_ALERT\s+'
    r'detector=(?P<detector>\d+)\s+'
    r'suspect=(?P<suspect>[^\s]+)\s+'
    r'type=(?P<type>\w+)\s+'
    r'source=(?P<source>\w+)\s+'
    r'alerts=(?P<alerts>\d+)\s+'
    r'dio_rate=(?P<dio_rate>-?\d+)\s+'
    r'version_delta=(?P<version_delta>-?\d+)\s+'
    r'rank=(?P<rank>-?\d+)\s+'
    r'rank_delta=(?P<rank_delta>-?\d+)\s+'
    r'is_poison=(?P<is_poison>-?\d+)'
)

# Also parse node ID from Cooja log prefix: "ID:XX"
NODE_ID_PATTERN = re.compile(r'ID:(?P<node_id>\d+)')


def process_ml_alert(match, raw_line, node_id=None):
    """Process a parsed ML_ALERT and route it through ACL engine"""
    global stats

    timestamp = time.time()
    
    alert = {
        'timestamp': timestamp,
        'time_str': datetime.now().strftime('%H:%M:%S'),
        'detector_id': int(match.group('detector')),
        'suspect_addr': match.group('suspect').strip(),
        'attack_type': match.group('type'),
        'detection_source': match.group('source'),
        'consecutive_alerts': int(match.group('alerts')),
        'features': {
            'dio_rate': int(match.group('dio_rate')),
            'version_delta': int(match.group('version_delta')),
            'rank': int(match.group('rank')),
            'rank_delta': int(match.group('rank_delta')),
            'is_poison': int(match.group('is_poison')),
        },
        'node_id': node_id,
        'raw_line': raw_line.strip(),
        'status': 'pending',
        'acl_decision': None,
    }

    # Add to global alert list
    ml_alerts.appendleft(alert)
    stats['total_alerts'] += 1

    # Update suspect profile
    suspect = alert['suspect_addr']
    profile = suspect_profiles[suspect]
    
    # Whitelist check: Trusted sinks/gateways must NEVER be blocked
    if is_trusted_suspect(suspect):
        alert['status'] = 'ignored_trusted'
        alert['acl_decision'] = 'IGNORED: Trusted Sink/Root gateway'
        logger.info(f"[TRUSTED] Alert ignored for trusted gateway: {suspect}")
        return

    if profile['first_seen'] is None:
        profile['first_seen'] = timestamp
    profile['last_seen'] = timestamp
    profile['total_alerts'] += 1
    profile['alert_sources'][alert['detection_source']] += 1
    profile['attack_types'][alert['attack_type']] += 1
    if node_id:
        profile['reporting_nodes'].add(node_id)
    elif alert['detector_id']:
        profile['reporting_nodes'].add(str(alert['detector_id']))
    
    features = alert['features']
    profile['max_dio_rate'] = max(profile['max_dio_rate'], features['dio_rate'])
    profile['max_rank_delta'] = max(profile['max_rank_delta'], features['rank_delta'])
    profile['max_version_delta'] = max(profile['max_version_delta'], features['version_delta'])
    profile['max_consecutive'] = max(profile['max_consecutive'], alert['consecutive_alerts'])
    profile['latest_features'] = features

    # Skip if already blocked or rejected
    if suspect in approved_blocks:
        alert['status'] = 'already_blocked'
        alert['acl_decision'] = 'SKIP (already blocked)'
        return
    
    if suspect in rejected_alerts:
        # Check if rejection has expired
        if timestamp - rejected_alerts[suspect].get('timestamp', 0) < ACL_CONFIG['alert_expiry_seconds']:
            alert['status'] = 'rejected'
            alert['acl_decision'] = 'SKIP (rejected by supervisor)'
            return
        else:
            # Rejection expired, allow re-evaluation
            del rejected_alerts[suspect]

    # ==============================
    # ACL AUTO-APPROVE ENGINE
    # ==============================
    auto_reason = acl_auto_evaluate(alert, profile)
    
    if auto_reason:
        # Auto-approve: block this suspect
        alert['status'] = 'auto_approved'
        alert['acl_decision'] = f'AUTO-APPROVED: {auto_reason}'
        
        approve_block(suspect, alert, auto_reason, is_auto=True)
        logger.warning(f"[ACL AUTO-APPROVED] block for {suspect}: {auto_reason}")
    else:
        # Needs human review
        alert['status'] = 'pending'
        alert['acl_decision'] = 'PENDING: Awaiting supervisor review'
        pending_alerts[suspect] = alert
        profile['status'] = 'pending'
        logger.info(f"[PENDING] Alert pending review for {suspect} (type={alert['attack_type']}, "
                     f"dio_rate={features['dio_rate']}, alerts={alert['consecutive_alerts']})")


def acl_auto_evaluate(alert, profile):
    """
    ACL Auto-Approve Engine with Multi-Observer Spatial Consensus.
    To avoid false positives, auto-approve requires:
      - Either MULTI-DETECTOR consensus (>=2 observers confirm the attack)
      - OR EXTREME metrics sustained over multiple consecutive alerts
    """
    features = alert['features']
    cfg = ACL_CONFIG
    
    # Priority 1: Multi-detector spatial consensus (High confidence in WSN broadcast)
    if len(profile['reporting_nodes']) >= 2 and profile['total_alerts'] >= 4:
        return f"multi_detector consensus: {len(profile['reporting_nodes'])} observers reported ({profile['total_alerts']} alerts)"

    # Priority 2: Clear, sustained Carousel DIO flood
    if features['dio_rate'] >= cfg['auto_approve_dio_rate'] and alert['consecutive_alerts'] >= cfg['auto_approve_consecutive_alerts']:
        return f"sustained carousel flood: dio_rate={features['dio_rate']}, alerts={alert['consecutive_alerts']}"

    # Priority 3: Clear, sustained Stretch attack
    if features['rank_delta'] >= cfg['auto_approve_rank_delta'] and alert['consecutive_alerts'] >= cfg['auto_approve_consecutive_alerts']:
        return f"sustained stretch attack: rank_delta={features['rank_delta']}, alerts={alert['consecutive_alerts']}"

    # Priority 4: Clear Version Number Attack (version delta >= 5)
    if features['version_delta'] >= cfg['auto_approve_version_delta'] and alert['consecutive_alerts'] >= 2:
        return f"version_delta={features['version_delta']} >= {cfg['auto_approve_version_delta']}"

    return None


# ============================================================
# THREAT ASSESSMENT ENGINE
# Generates human-readable threat analysis for non-expert operators
# ============================================================

# Attack type knowledge base - plain Vietnamese explanations
ATTACK_KNOWLEDGE_BASE = {
    'CAROUSEL': {
        'name': 'Carousel (Xoay vong)',
        'icon': '',
        'description': 'Node lien tuc phat tin hieu DIO voi toc do bat thuong, buoc cac node xung quanh phai xu ly lien tuc, gay tieu hao nang luong hang loat.',
        'impact': 'Lam can pin toan bo cac node lan can trong vai gio thay vi vai thang.',
        'normal_range': 'DIO rate binh thuong: 1-10 goi/phut',
    },
    'STRETCH': {
        'name': 'Stretch (Keo gian)',
        'icon': '',
        'description': 'Node gia mao thong tin cap bac dinh tuyen (Rank) rat cao, khien cac goi tin bi dan di duong vong dai hon can thiet.',
        'impact': 'Tang gap 3-5 lan quang duong truyen tin, hao pin nhanh va tang do tre.',
        'normal_range': 'Rank delta binh thuong: 0-128',
    },
    'STEALTH': {
        'name': 'Stealth (Tang hinh)',
        'icon': '',
        'description': 'Node tan cong hoat dong voi cuong do thap, kho phat hien bang nguong don gian. Can ML de nhan dien qua to hop nhieu chi so nhe.',
        'impact': 'Lam suy yeu mang tu tu, kho phat hien cho den khi thiet hai nghiem trong.',
        'normal_range': 'Nhieu chi so hoi bat thuong nhung chua vuot nguong don le',
    },
    'COORDINATED': {
        'name': 'Coordinated (Phoi hop)',
        'icon': '',
        'description': 'Nhieu hanh vi tan cong xay ra dong thoi: vua thay doi phien ban RPL, vua thao tung Rank.',
        'impact': 'Cuc ky nguy hiem - gay bat on toan bo cau truc dinh tuyen mang.',
        'normal_range': 'Khong bao gio co nhieu chi so bat thuong cung luc o node binh thuong',
    },
}

def generate_threat_assessment(alert_data, profile):
    """
    Generate a comprehensive threat assessment for a pending alert.
    Returns a dict with threat_level, confidence, explanation, recommendation, evidence.
    Designed so non-expert operators can make informed decisions.
    """
    features = alert_data.get('features', {})
    attack_type = alert_data.get('attack_type', 'UNKNOWN')
    consecutive = alert_data.get('consecutive_alerts', 0)
    total_alerts = profile.get('total_alerts', 0) if isinstance(profile, dict) else 0
    reporting_nodes = profile.get('reporting_nodes', set()) if isinstance(profile, dict) else set()
    num_reporters = len(reporting_nodes) if isinstance(reporting_nodes, set) else len(reporting_nodes)
    detection_source = alert_data.get('detection_source', 'UNKNOWN')
    
    dio_rate = features.get('dio_rate', 0)
    version_delta = features.get('version_delta', 0)
    rank = features.get('rank', 0)
    rank_delta = features.get('rank_delta', 0)
    is_poison = features.get('is_poison', 0)

    # ---- STEP 1: Compute confidence score (0-100) ----
    confidence = 0
    evidence_points = []

    # Evidence from detection source
    if detection_source == 'ML':
        confidence += 25
        evidence_points.append({
            'icon': '[ML]',
            'text': 'Mo hinh ML (Decision Tree) nhan dien hanh vi bat thuong',
            'weight': 'high',
        })
    elif detection_source == 'HEURISTIC':
        confidence += 15
        evidence_points.append({
            'icon': '[HEU]',
            'text': 'Quy tac nguong cung (Heuristic) phat hien vi pham',
            'weight': 'medium',
        })

    # Evidence from DIO rate
    if dio_rate >= 50:
        confidence += 25
        evidence_points.append({
            'icon': '[!!!]',
            'text': f'Toc do DIO cuc cao: {dio_rate} goi/phut (binh thuong: 1-10)',
            'weight': 'critical',
        })
    elif dio_rate >= 20:
        confidence += 15
        evidence_points.append({
            'icon': '[!!]',
            'text': f'Toc do DIO cao bat thuong: {dio_rate} goi/phut (binh thuong: 1-10)',
            'weight': 'high',
        })
    elif dio_rate >= 10:
        confidence += 5
        evidence_points.append({
            'icon': '[!]',
            'text': f'Toc do DIO hoi cao: {dio_rate} goi/phut (gioi han tren binh thuong)',
            'weight': 'low',
        })

    # Evidence from rank_delta
    if rank_delta >= 500:
        confidence += 20
        evidence_points.append({
            'icon': '[!!!]',
            'text': f'Rank nhay vot: D{rank_delta} (binh thuong: 0-128, nguong nguy hiem: >500)',
            'weight': 'critical',
        })
    elif rank_delta >= 200:
        confidence += 12
        evidence_points.append({
            'icon': '[!!]',
            'text': f'Rank thay doi lon: D{rank_delta} (binh thuong: 0-128)',
            'weight': 'high',
        })
    elif rank_delta >= 100:
        confidence += 5
        evidence_points.append({
            'icon': '[!]',
            'text': f'Rank dao dong: D{rank_delta} (co the do chuyen mach parent)',
            'weight': 'low',
        })

    # Evidence from version_delta
    if version_delta >= 5:
        confidence += 20
        evidence_points.append({
            'icon': '[!!!]',
            'text': f'Phien ban RPL thay doi {version_delta} lan (binh thuong: 0-1, nguong nguy hiem: >=5)',
            'weight': 'critical',
        })
    elif version_delta >= 2:
        confidence += 10
        evidence_points.append({
            'icon': '[!!]',
            'text': f'Phien ban RPL thay doi {version_delta} lan (binh thuong: 0-1)',
            'weight': 'high',
        })

    # Evidence from poison flag
    if is_poison:
        confidence += 15
        evidence_points.append({
            'icon': '[POI]',
            'text': 'Phat hien co Route Poisoning (Rank = vo han) -- hanh vi co y pha hoai',
            'weight': 'critical',
        })

    # Evidence from consecutive alerts
    if consecutive >= 4:
        confidence += 10
        evidence_points.append({
            'icon': '[RPT]',
            'text': f'Hanh vi lap lai {consecutive} lan lien tiep -- khong phai su co ngau nhien',
            'weight': 'high',
        })
    elif consecutive >= 2:
        confidence += 5
        evidence_points.append({
            'icon': '[RPT]',
            'text': f'Hanh vi lap lai {consecutive} lan -- can theo doi',
            'weight': 'medium',
        })

    # Evidence from multi-detector consensus
    if num_reporters >= 3:
        confidence += 15
        evidence_points.append({
            'icon': '[CON]',
            'text': f'{num_reporters} node khac nhau cung bao cao -- dong thuan cao',
            'weight': 'critical',
        })
    elif num_reporters >= 2:
        confidence += 10
        evidence_points.append({
            'icon': '[CON]',
            'text': f'{num_reporters} node khac nhau cung bao cao doi tuong nay',
            'weight': 'high',
        })

    # Cap confidence at 100
    confidence = min(confidence, 100)

    # ---- STEP 2: Determine threat level ----
    if confidence >= 80:
        threat_level = 'CRITICAL'
        threat_color = '#ef4444'
        threat_label = 'Nguy Hiểm Cao'
    elif confidence >= 55:
        threat_level = 'HIGH'
        threat_color = '#f97316'
        threat_label = 'Nguy Hiểm'
    elif confidence >= 35:
        threat_level = 'MEDIUM'
        threat_color = '#eab308'
        threat_label = 'Nghi Vấn'
    else:
        threat_level = 'LOW'
        threat_color = '#22c55e'
        threat_label = 'Thấp'

    # ---- STEP 3: Generate recommendation ----
    if confidence >= 75:
        recommendation = 'BLOCK'
        rec_text = 'Khuyen nghi CHAN ngay -- Bang chung ro rang, rui ro cao neu khong hanh dong.'
        rec_detail = 'He thong co du bang chung de xac nhan day la hanh vi tan cong. Cho them co the gay thiet hai nang luong cho cac node lan can.'
    elif confidence >= 45:
        recommendation = 'LIKELY_BLOCK'
        rec_text = 'Nhieu kha nang nen CHAN -- Kiem tra them bang chung ben duoi truoc khi quyet dinh.'
        rec_detail = 'Co nhieu dau hieu dang ngo nhung chua hoan toan chac chan. Xem xet cac chi so chi tiet ben duoi.'
    elif confidence >= 25:
        recommendation = 'MONITOR'
        rec_text = 'Nen THEO DOI them -- Chua du bang chung de chan, co the la su co tam thoi.'
        rec_detail = 'Cac chi so hoi bat thuong nhung co the do nhieu mang hoac thay doi topology tu nhien. Doi them du lieu.'
    else:
        recommendation = 'DISMISS'
        rec_text = 'Co the BO QUA -- Muc do bat thuong thap, nhieu kha nang la bao dong nham.'
        rec_detail = 'Cac chi so gan nhu nam trong pham vi binh thuong. Co the do node moi gia nhap mang hoac dao dong tu nhien.'

    # ---- STEP 4: Generate plain-language explanation ----
    attack_info = ATTACK_KNOWLEDGE_BASE.get(attack_type.upper(), {
        'name': attack_type,
        'icon': '',
        'description': f'Phat hien hanh vi bat thuong loai {attack_type} tu node nghi van.',
        'impact': 'Co the gay anh huong den hoat dong binh thuong cua mang.',
        'normal_range': 'Dang danh gia...',
    })

    explanation = (
        f"{attack_info['icon']} **{attack_info['name']}**\n\n"
        f"**Đang xảy ra gì?** {attack_info['description']}\n\n"
        f"**Ảnh hưởng nếu không chặn:** {attack_info['impact']}\n\n"
        f"**Phạm vi bình thường:** {attack_info['normal_range']}"
    )

    return {
        'threat_level': threat_level,
        'threat_label': threat_label,
        'threat_color': threat_color,
        'confidence_score': confidence,
        'recommendation': recommendation,
        'recommendation_text': rec_text,
        'recommendation_detail': rec_detail,
        'explanation': explanation,
        'attack_info': {
            'name': attack_info['name'],
            'icon': attack_info['icon'],
            'description': attack_info['description'],
            'impact': attack_info['impact'],
            'normal_range': attack_info['normal_range'],
        },
        'evidence': [{'icon': e['icon'], 'text': e['text'], 'weight': e['weight']} for e in evidence_points],
    }


def approve_block(suspect, alert, reason, is_auto=False):
    """Approve blocking a suspect node"""
    global stats
    
    block_info = {
        'suspect_addr': suspect,
        'attack_type': alert['attack_type'],
        'reason': reason,
        'approved_at': time.time(),
        'approved_at_str': datetime.now().strftime('%H:%M:%S'),
        'is_auto': is_auto,
        'expires_at': time.time() + ACL_CONFIG['block_duration_seconds'],
        'features': alert['features'],
        'total_alerts_at_block': suspect_profiles[suspect]['total_alerts'],
    }
    
    approved_blocks[suspect] = block_info
    suspect_profiles[suspect]['status'] = 'blocked'
    
    if suspect in pending_alerts:
        del pending_alerts[suspect]
    
    if is_auto:
        auto_approved.appendleft(block_info)
        stats['total_auto_approved'] += 1
    else:
        stats['total_manual_approved'] += 1
    
    # Write block command to file bridge for Cooja to pick up
    write_block_command(suspect, alert['attack_type'])


def write_block_command(suspect_addr, attack_type):
    """Write block command to file bridge"""
    try:
        os.makedirs(os.path.dirname(BLOCK_CMD_FILE), exist_ok=True)
        
        # Append to existing blocks (multiple blocks possible)
        with open(BLOCK_CMD_FILE, 'a') as f:
            f.write(f"BLOCK {suspect_addr} {attack_type} {int(time.time())}\n")
        
        logger.info(f"Block command written for {suspect_addr} ({attack_type})")
    except Exception as e:
        logger.error(f"Failed to write block command: {e}")


# ============================================================
# LOG FILE WATCHER
# ============================================================

class MLLogWatcher(threading.Thread):
    """Thread to watch Cooja log file for ML_ALERT lines"""
    
    def __init__(self, log_file_path):
        super().__init__(daemon=True)
        self.log_file_path = log_file_path
        self.running = True
    
    def run(self):
        while self.running:
            logger.info(f"Watching log file: {self.log_file_path}")
            try:
                with open(self.log_file_path, 'r') as f:
                    # Read existing lines
                    line_count = 0
                    alert_count = 0
                    for line in f:
                        if 'ML_ALERT' in line:
                            self.process_alert_line(line)
                            alert_count += 1
                        line_count += 1
                    
                    logger.info(f"Processed {line_count} existing lines, found {alert_count} ML alerts")
                    
                    # Tail mode: watch for new lines
                    while self.running:
                        line = f.readline()
                        if line:
                            if 'ML_ALERT' in line:
                                self.process_alert_line(line)
                        else:
                            # Check for log rotation
                            try:
                                log_dir = os.path.dirname(self.log_file_path)
                                all_logs = glob.glob(os.path.join(log_dir, 'run_*.log'))
                                if all_logs:
                                    latest_file = max(all_logs, key=os.path.getctime)
                                    if latest_file != self.log_file_path:
                                        logger.info(f"Log rotated! Switching to: {latest_file}")
                                        self.log_file_path = latest_file
                                        break
                            except Exception:
                                pass
                            threading.Event().wait(0.5)
            
            except FileNotFoundError:
                logger.warning(f"Log file not found: {self.log_file_path}, retrying...")
                threading.Event().wait(2)
            except Exception as e:
                logger.error(f"Error watching log file: {e}")
                threading.Event().wait(2)
    
    def process_alert_line(self, line):
        """Parse an ML_ALERT line and process it"""
        # Extract node ID from Cooja prefix
        node_match = NODE_ID_PATTERN.search(line)
        node_id = node_match.group('node_id') if node_match else None
        
        # Parse ML_ALERT
        alert_match = ML_ALERT_PATTERN.search(line)
        if alert_match:
            process_ml_alert(alert_match, line, node_id)
    
    def stop(self):
        self.running = False


# ============================================================
# PERIODIC CLEANUP
# ============================================================

def periodic_cleanup():
    """Clean up expired blocks and stale alerts"""
    while True:
        now = time.time()
        
        # Expire old blocks
        expired_blocks = [addr for addr, info in approved_blocks.items()
                          if now > info['expires_at']]
        for addr in expired_blocks:
            logger.info(f"Block expired for {addr}")
            del approved_blocks[addr]
            if addr in suspect_profiles:
                suspect_profiles[addr]['status'] = 'expired'
            stats['total_expired'] += 1
        
        # Expire old pending alerts
        expired_pending = [addr for addr, alert in pending_alerts.items()
                           if now - alert['timestamp'] > ACL_CONFIG['alert_expiry_seconds']]
        for addr in expired_pending:
            logger.info(f"Pending alert expired for {addr}")
            del pending_alerts[addr]
            if addr in suspect_profiles:
                suspect_profiles[addr]['status'] = 'expired'
        
        threading.Event().wait(30)  # Check every 30 seconds


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('ml_monitor.html')


@app.route('/api/ml/dashboard')
def get_dashboard_data():
    """Main API endpoint for the dashboard"""
    now = time.time()
    
    # Build pending list with enriched profile data + threat assessment
    pending_list = []
    for addr, alert in pending_alerts.items():
        profile = suspect_profiles.get(addr, {})
        threat = generate_threat_assessment(alert, profile)
        pending_list.append({
            'suspect_addr': addr,
            'attack_type': alert['attack_type'],
            'detection_source': alert['detection_source'],
            'consecutive_alerts': alert['consecutive_alerts'],
            'features': alert['features'],
            'time_str': alert['time_str'],
            'detector_id': alert.get('detector_id'),
            'node_id': alert.get('node_id'),
            'age_seconds': int(now - alert['timestamp']),
            # Profile enrichment
            'total_alerts': profile.get('total_alerts', 0),
            'reporting_nodes': list(profile.get('reporting_nodes', set())),
            'max_dio_rate': profile.get('max_dio_rate', 0),
            'max_rank_delta': profile.get('max_rank_delta', 0),
            'max_version_delta': profile.get('max_version_delta', 0),
            'max_consecutive': profile.get('max_consecutive', 0),
            'attack_types': dict(profile.get('attack_types', {})),
            # Threat assessment for decision support
            'threat': threat,
        })
    
    # Build blocked list
    blocked_list = []
    for addr, info in approved_blocks.items():
        remaining = max(0, int(info['expires_at'] - now))
        blocked_list.append({
            'suspect_addr': addr,
            'attack_type': info['attack_type'],
            'reason': info['reason'],
            'approved_at_str': info['approved_at_str'],
            'is_auto': info['is_auto'],
            'remaining_seconds': remaining,
            'features': info['features'],
            'total_alerts_at_block': info.get('total_alerts_at_block', 0),
        })
    
    # Recent alerts (last 50)
    recent_alerts = []
    for alert in list(ml_alerts)[:50]:
        recent_alerts.append({
            'time_str': alert['time_str'],
            'suspect_addr': alert['suspect_addr'],
            'attack_type': alert['attack_type'],
            'detection_source': alert['detection_source'],
            'consecutive_alerts': alert['consecutive_alerts'],
            'features': alert['features'],
            'status': alert['status'],
            'acl_decision': alert['acl_decision'],
            'detector_id': alert.get('detector_id'),
        })
    
    # Auto-approved log (last 20)
    auto_log = []
    for info in list(auto_approved)[:20]:
        auto_log.append({
            'suspect_addr': info['suspect_addr'],
            'attack_type': info['attack_type'],
            'reason': info['reason'],
            'approved_at_str': info['approved_at_str'],
        })
    
    return jsonify({
        'pending': pending_list,
        'blocked': blocked_list,
        'recent_alerts': recent_alerts,
        'auto_approved_log': auto_log,
        'stats': stats,
        'acl_config': ACL_CONFIG,
        'timestamp': now,
    })


@app.route('/api/ml/approve', methods=['POST'])
def approve_suspect():
    """Supervisor approves blocking a suspect node"""
    data = request.get_json()
    suspect_addr = data.get('suspect_addr')
    
    if not suspect_addr:
        return jsonify({'status': 'error', 'message': 'Missing suspect_addr'}), 400
    
    if suspect_addr not in pending_alerts:
        return jsonify({'status': 'error', 'message': f'{suspect_addr} not in pending list'}), 404
    
    alert = pending_alerts[suspect_addr]
    reason = data.get('reason', 'Manual approval by supervisor')
    
    approve_block(suspect_addr, alert, reason, is_auto=False)
    
    logger.warning(f"[SUPERVISOR APPROVED] block for {suspect_addr}: {reason}")
    
    return jsonify({
        'status': 'success',
        'message': f'Node {suspect_addr} has been blocked',
        'suspect_addr': suspect_addr,
    })


@app.route('/api/ml/reject', methods=['POST'])
def reject_suspect():
    """Supervisor rejects blocking a suspect node (false positive)"""
    global stats
    
    data = request.get_json()
    suspect_addr = data.get('suspect_addr')
    
    if not suspect_addr:
        return jsonify({'status': 'error', 'message': 'Missing suspect_addr'}), 400
    
    reason = data.get('reason', 'Rejected by supervisor (false positive)')
    
    rejected_alerts[suspect_addr] = {
        'suspect_addr': suspect_addr,
        'reason': reason,
        'timestamp': time.time(),
        'rejected_at_str': datetime.now().strftime('%H:%M:%S'),
    }
    
    if suspect_addr in pending_alerts:
        del pending_alerts[suspect_addr]
    
    if suspect_addr in suspect_profiles:
        suspect_profiles[suspect_addr]['status'] = 'rejected'
    
    stats['total_rejected'] += 1
    
    logger.info(f"[SUPERVISOR REJECTED] alert for {suspect_addr}: {reason}")
    
    return jsonify({
        'status': 'success',
        'message': f'Alert for {suspect_addr} rejected (marked as false positive)',
        'suspect_addr': suspect_addr,
    })


@app.route('/api/ml/unblock', methods=['POST'])
def unblock_suspect():
    """Supervisor manually unblocks a node"""
    data = request.get_json()
    suspect_addr = data.get('suspect_addr')
    
    if not suspect_addr:
        return jsonify({'status': 'error', 'message': 'Missing suspect_addr'}), 400
    
    if suspect_addr in approved_blocks:
        del approved_blocks[suspect_addr]
        if suspect_addr in suspect_profiles:
            suspect_profiles[suspect_addr]['status'] = 'unblocked'
        
        # Write unblock command
        try:
            os.makedirs(os.path.dirname(BLOCK_CMD_FILE), exist_ok=True)
            with open(BLOCK_CMD_FILE, 'a') as f:
                f.write(f"UNBLOCK {suspect_addr} {int(time.time())}\n")
        except Exception as e:
            logger.error(f"Failed to write unblock command: {e}")
        
        logger.info(f"[SUPERVISOR UNBLOCKED] {suspect_addr}")
        return jsonify({'status': 'success', 'message': f'{suspect_addr} unblocked'})
    
    return jsonify({'status': 'error', 'message': f'{suspect_addr} not in blocked list'}), 404


@app.route('/api/ml/config', methods=['GET', 'POST'])
def manage_acl_config():
    """Get or update ACL auto-approve configuration"""
    if request.method == 'GET':
        return jsonify(ACL_CONFIG)
    
    data = request.get_json()
    for key in ['auto_approve_consecutive_alerts', 'auto_approve_dio_rate',
                'auto_approve_rank_delta', 'auto_approve_version_delta',
                'alert_expiry_seconds', 'block_duration_seconds']:
        if key in data:
            ACL_CONFIG[key] = int(data[key])
            logger.info(f"ACL config updated: {key} = {data[key]}")
    
    return jsonify({'status': 'success', 'config': ACL_CONFIG})


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    print("=" * 70)
    print("ML DEFENSE MONITOR SERVER")
    print("=" * 70)
    print()
    print("This server monitors ML-based vampire attack detection alerts")
    print("and provides a dashboard for human supervisors to approve/reject")
    print("node blocking decisions.")
    print()
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    # Check for log file argument
    if len(sys.argv) > 1:
        log_path = Path(sys.argv[1])
        log_dir = log_path.parent
        
        if log_dir.exists():
            all_logs = glob.glob(os.path.join(log_dir, 'run_*.log'))
            all_logs.extend(glob.glob(os.path.join(log_dir, 'run.log')))
            
            if all_logs:
                latest_log = max(all_logs, key=os.path.getctime)
                logger.info(f"Starting ML alert watcher on: {os.path.basename(latest_log)}")
                watcher = MLLogWatcher(latest_log)
                watcher.start()
            else:
                logger.warning(f"No log files found in {log_dir}")
                # Create a watcher anyway for when logs appear
                default_log = os.path.join(log_dir, 'run_1.log')
                watcher = MLLogWatcher(default_log)
                watcher.start()
        else:
            logger.warning(f"Log directory not found: {log_dir}")
    else:
        logger.info("No log file specified. Server will run in API-only mode")
        logger.info("Usage: python ml_monitor_server.py [path_to_log_file]")
    
    print(f"Dashboard: http://localhost:5003")
    print(f"API: http://localhost:5003/api/ml/dashboard")
    print()
    print("ACL Auto-Approve Thresholds:")
    for key, val in ACL_CONFIG.items():
        print(f"  {key}: {val}")
    print()
    print("Press CTRL+C to stop the server")
    print("=" * 70)
    
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)
