import numpy as np
from collections import deque
import datetime
import time
import logging

# Configure debug logger
dl = logging.getLogger('DefenseDebug')
dl.setLevel(logging.DEBUG)
fh = logging.FileHandler(r'e:\Projects\Projects\WSN_dacntt\wsn_dacntt\src\defense_debug.log', mode='a')
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh.setFormatter(formatter)
dl.addHandler(fh)
dl.debug('Defense module loaded and logger initialized!')


class SybilDetector:
    def __init__(self):
        # Whitelist: node_id -> [list of historical rssi values]
        self.whitelist = {}
        # Pre-calculated profile: node_id -> average historical rssi
        self.profile = {}
        # Probation profile cho các node mới xuất hiện
        self.probation_profile = {}
        
    def learn(self, node_id, rssi):
        if node_id not in self.whitelist:
            self.whitelist[node_id] = []
        self.whitelist[node_id].append(rssi)
        
    def finalize_learning(self):
        # Build profile average for each node
        for nid, rssi_list in self.whitelist.items():
            self.profile[nid] = sum(rssi_list) / len(rssi_list)
            
    def check(self, node_id, rssi):
        # 1. Unknown Node ID -> Đưa vào diện theo dõi (Probation)
        if node_id not in self.profile:
            if node_id not in self.probation_profile:
                self.probation_profile[node_id] = []
            self.probation_profile[node_id].append(rssi)
            
            # Kẻ tấn công Sybil thường tạo ra NHIỀU ID giả mạo từ CÙNG 1 vị trí vật lý
            # Nếu phát hiện nhiều tân binh có chung mức RSSI -> Chắc chắn là đám Clone Sybil
            current_avg = np.mean(self.probation_profile[node_id])
            for other_id, other_rssi_list in self.probation_profile.items():
                if other_id != node_id:
                    other_avg = np.mean(other_rssi_list)
                    if abs(current_avg - other_avg) < 2.0:
                        return False, f"Sybil Clone (RSSI {current_avg:.1f} matches Node {other_id})"
                        
            return True, "Probation (New Node)"
            
        # 2. Known Node ID -> RSSI Jump Check (Giãn threshold thành 3.0 do có Gaussian Noise)
        historical_rssi = self.profile[node_id]
        if abs(historical_rssi - rssi) > 3.0:
            return False, f"RSSI anomaly > 3dBm (Expected: {historical_rssi:.1f}, Got: {rssi})"
            
        # Optional: continuously update profile slowly
        self.profile[node_id] = (self.profile[node_id] * 0.9) + (rssi * 0.1)
        return True, ""

class FDIDetector:
    def __init__(self, window_size=20):
        self.window = deque(maxlen=window_size)
        
    def check(self, temp_c):
        if len(self.window) < 5:
            self.window.append(temp_c)
            return True
            
        mu = np.mean(self.window)
        sigma = np.std(self.window)
        if sigma == 0:
            sigma = 1.0
            
        if abs(temp_c - mu) > 3 * sigma:
            return False
            
        self.window.append(temp_c)
        return True

class TrustManager:
    def __init__(self):
        self.trust_db = {}
        
    def get_trust(self, node_id):
        if node_id not in self.trust_db:
            self.trust_db[node_id] = {'alpha': 10.0, 'beta': 1.0, 'blacklisted': False}
        record = self.trust_db[node_id]
        return (record['alpha'] / (record['alpha'] + record['beta'])) * 100.0
        
    def is_blacklisted(self, node_id):
        if node_id not in self.trust_db:
            return False
        return self.trust_db[node_id]['blacklisted']
        
    def update_trust(self, node_id, sybil_passed, fdi_passed):
        if node_id not in self.trust_db:
            self.trust_db[node_id] = {'alpha': 10.0, 'beta': 1.0, 'blacklisted': False}
            
        record = self.trust_db[node_id]
        if record['blacklisted']:
            return True # Vẫn đang bị block
            
        if sybil_passed and fdi_passed:
            record['alpha'] += 1.0
        else:
            # Trừ điểm từ từ thay vì block ngay
            if not fdi_passed:
                record['beta'] += 2.0
            if not sybil_passed:
                record['beta'] += 4.0
            
        trust = (record['alpha'] / (record['alpha'] + record['beta'])) * 100.0
        if trust < 40.0:
            record['blacklisted'] = True
            
        return record['blacklisted']

class DefenseSystem:
    def __init__(self):
        self.sybil_detector = SybilDetector()
        self.fdi_detector = FDIDetector()
        self.trust_manager = TrustManager()
        self.defense_logs = deque(maxlen=10)
        self.packet_count = 0
        self.learning_duration_pkts = 250 # ~5 mins of normal traffic (50 nodes * 1 pkt/min)
        self.learning_finalized = False
        
    def log_event(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.defense_logs.append(f"[{ts}] {msg}")
        
    def process_packet(self, node_id, rssi, temp_c):
        self.packet_count += 1
        is_learning = self.packet_count < self.learning_duration_pkts
        
        if is_learning:
            # Phase 1: LEARNING
            self.sybil_detector.learn(node_id, rssi)
            self.fdi_detector.check(temp_c) # Just to fill window
            if self.packet_count % 50 == 0:
                self.log_event(f"Learning... {self.packet_count}/{self.learning_duration_pkts} packets")
                try:
                    dl.debug(f"LEARNING: Packet {self.packet_count}/{self.learning_duration_pkts} - Node {node_id} RSSI={rssi} Temp={temp_c}")
                except Exception:
                    pass
            return True # Everything passes during learning
            
        # Transition to Armed Phase
        if not self.learning_finalized:
            self.sybil_detector.finalize_learning()
            self.learning_finalized = True
            self.log_event("SYSTEM ARMED. Profiling complete.")
            try:
                dl.debug(f"SYSTEM ARMED. Profile Baseline: {self.sybil_detector.profile}")
            except Exception:
                pass
            
        # Phase 2: ARMED
        if self.trust_manager.is_blacklisted(node_id):
            try:
                dl.debug(f"DROP: Node {node_id} is already blacklisted.")
            except Exception:
                pass
            return False
            
        sybil_passed, sybil_reason = self.sybil_detector.check(node_id, rssi)
        fdi_passed = self.fdi_detector.check(temp_c)
        
        passed = sybil_passed and fdi_passed
        try:
            dl.debug(f"CHECK: Node={node_id}, RSSI={rssi}, Temp={temp_c} -> Passed_Sybil={sybil_passed} ({sybil_reason}), Passed_FDI={fdi_passed}")
        except Exception:
            pass
        
        if not sybil_passed:
            self.log_event(f"Sybil Warning: Node {node_id} - {sybil_reason}")
        if not fdi_passed:
            self.log_event(f"FDI Warning: Node {node_id} sent anomalous temp ({temp_c}C)")
            
        blacklisted = self.trust_manager.update_trust(node_id, sybil_passed, fdi_passed)
        
        if blacklisted:
            self.log_event(f"BLACKLISTED: Node {node_id} trust fell below 40%")
            try:
                dl.debug(f"BLACKLISTED: Node {node_id}")
            except Exception:
                pass
            return False
            
        return True

    def get_ui_data(self):
        ui_trust = {}
        for nid, rec in self.trust_manager.trust_db.items():
            trust_val = (rec['alpha'] / (rec['alpha'] + rec['beta'])) * 100.0
            ui_trust[str(nid)] = {
                'score': round(trust_val, 1),
                'blacklisted': rec['blacklisted']
            }
            
        return {
            'trust_db': ui_trust, 
            'logs': list(self.defense_logs),
            'learning_pkts_left': max(0, self.learning_duration_pkts - self.packet_count),
            'learning_pkts_total': self.learning_duration_pkts,
            'is_armed': self.learning_finalized
        }