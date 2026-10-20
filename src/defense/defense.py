import numpy as np
import math
from collections import deque
import glob
import os
import xml.etree.ElementTree as ET

def load_topology_map(attacks_dir):
    try:
        # --- HARDCODED SCENARIO ---
        target_csc = os.path.join(attacks_dir, "wsn-2sink-hijacked.csc")
        if not os.path.exists(target_csc):
            print("Could not find wsn-2sink-hijacked.csc")
            return {}
        
        print(f"Loading topology from: {os.path.basename(target_csc)}")
        
        tree = ET.parse(target_csc)
        root = tree.getroot()
        
        coords = {}
        for mote in root.findall('.//mote'):
            mote_id = None
            x, y = None, None
            for intf in mote.findall('interface_config'):
                text = intf.text.strip() if intf.text else ""
                if "org.contikios.cooja.interfaces.Position" in text:
                    pos = intf.find('pos')
                    if pos is not None:
                        x = float(pos.get('x'))
                        y = float(pos.get('y'))
                elif "org.contikios.cooja.contikimote.interfaces.ContikiMoteID" in text:
                    id_tag = intf.find('id')
                    if id_tag is not None:
                        mote_id = int(id_tag.text)
            
            if mote_id is not None and x is not None and y is not None:
                coords[mote_id] = (x, y)
        return coords
    except Exception as e:
        print(f"Error loading topology: {e}")
        return {}

import datetime
import time
import logging

# Configure debug logger
dl = logging.getLogger('DefenseDebug')
dl.setLevel(logging.DEBUG)
fh = logging.FileHandler(r'e:\Projects\Projects\WSN_dacntt\wsn_dacntt\src\defense_debug.log', mode='a', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh.setFormatter(formatter)
dl.addHandler(fh)
dl.debug('Defense module V4 (Inference Engine) loaded and logger initialized!')


class SybilDetector:
    def __init__(self):
        self.whitelist = {}
        self.profile = {}
        self.probation_profile = {}
        self.topology_map = {}
        self.rssi_blacklist = []
        self.rssi_violation_counter = {}
        self.rssi_blacklist_threshold = 3
        
    def learn(self, node_id, rssi):
        if node_id not in self.whitelist:
            self.whitelist[node_id] = []
        self.whitelist[node_id].append(rssi)

    def finalize_learning(self):
        dl.info(f"[SYS] LEARNING COMPLETE: Successfully profiled {len(self.whitelist)} Node.")
        for nid, rssi_list in self.whitelist.items():
            self.profile[nid] = sum(rssi_list) / len(rssi_list)
            dl.info(f"[PROFILE] Node {nid}: Baseline RSSI = {self.profile[nid]:.1f} dBm")
    def _rssi_bucket(self, rssi):
        return round(rssi / 2.0) * 2.0

    def is_rssi_blacklisted(self, rssi):
        bucket = self._rssi_bucket(rssi)
        for bl_rssi in self.rssi_blacklist:
            if abs(bucket - bl_rssi) <= 2.0:
                return True
        return False

    def record_rssi_violation(self, rssi):
        bucket = self._rssi_bucket(rssi)
        if bucket not in self.rssi_violation_counter:
            self.rssi_violation_counter[bucket] = 0
        self.rssi_violation_counter[bucket] += 1
        
        if self.rssi_violation_counter[bucket] >= self.rssi_blacklist_threshold:
            if not self.is_rssi_blacklisted(rssi):
                self.rssi_blacklist.append(bucket)
                return True
        return False
            
    def check(self, node_id, rssi):
        if node_id in self.profile:
            historical_rssi = self.profile[node_id]
            if abs(historical_rssi - rssi) > 3.0:
                return False, f"RSSI MISMATCH: Profile {historical_rssi:.1f} differs from actual {rssi:.1f}", "MISMATCH"
            self.profile[node_id] = (self.profile[node_id] * 0.9) + (rssi * 0.1)
            return True, "", "NONE"

        if self.is_rssi_blacklisted(rssi):
            bucket = self._rssi_bucket(rssi)
            anchor = bucket
            for bl_rssi in self.rssi_blacklist:
                if abs(bucket - bl_rssi) <= 2.0:
                    anchor = bl_rssi
                    break
            return False, f"ZONE BLOCK: Unknown ID from Blacklisted Zone [{anchor-2.0} to {anchor+2.0}]", "ZONE_BLOCK"
        
        if node_id not in self.profile:
            # Quick check: IDs above max known legitimate node are suspicious
            max_id = max(self.topology_map.keys()) if self.topology_map else (max(self.profile.keys()) if self.profile else 52)
            if node_id > max_id:
                return False, f"ID {node_id} not on coordinate map (Max ID = {max_id}). Spoofed identity!", "SYBIL_CLONE"
            if node_id not in self.probation_profile:
                self.probation_profile[node_id] = []
            self.probation_profile[node_id].append(rssi)
            
            current_avg = np.mean(self.probation_profile[node_id])
            for other_id, other_rssi_list in self.probation_profile.items():
                if other_id != node_id:
                    other_avg = np.mean(other_rssi_list)
                    if abs(current_avg - other_avg) < 2.0:
                        return False, f"SYBIL CLONE: ID nÃ y trÃ¹ng vá»‹ trÃ­ vá»›i nhiá»u ID áº£o khÃ¡c (RSSI ~{current_avg:.1f})", "SYBIL_CLONE"
                        
            return True, "Probation (New Node)", "NONE" 
            
        historical_rssi = self.profile[node_id]
        if abs(historical_rssi - rssi) > 3.0:
            return False, f"RSSI MISMATCH: Profiled {historical_rssi:.1f} but measured {rssi:.1f}", True
            
        self.profile[node_id] = (self.profile[node_id] * 0.9) + (rssi * 0.1)
        return True, "", False

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
        
    def update_trust(self, node_id, sybil_passed, fdi_passed, attack_type="NONE"):
        if node_id not in self.trust_db:
            self.trust_db[node_id] = {'alpha': 10.0, 'beta': 1.0, 'blacklisted': False}
            
        record = self.trust_db[node_id]
        if record['blacklisted']:
            return True
            
        if sybil_passed and fdi_passed:
            record['alpha'] += 1.0
        else:
            if not fdi_passed:
                if attack_type == "HIJACK":
                    # INSTANT KILL for Hijacked Nodes (Coordinated FDI)
                    record['alpha'] = 1.0
                    record['beta'] += 100.0
                else:
                    record['beta'] += 2.0
            if not sybil_passed:
                if attack_type in ["ZONE_BLOCK", "SYBIL_CLONE"]:
                    # INSTANT KILL for criminal (Ghost ID, No-fly zone)
                    record['alpha'] = 1.0
                    record['beta'] += 100.0
                else:
                    # Standard penalty for MISMATCH (Natural fluctuation or light Spoofing)
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
        self.defense_logs = deque(maxlen=50) # Increased capacity
        
        # UI Stats
        self.stats = {
            'spoof_blocked': 0,
            'fdi_blocked': 0,
            'bipolar_detected': 0
        }
        
        # Load Coordinate Map
        import os
        attacks_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'attacks')
        self.topology_map = load_topology_map(attacks_dir)
        print(f'[DEFENSE] Map loaded with {len(self.topology_map)} nodes.')
        
        topo_str = " | ".join([f"Node {nid}: ({x:.1f}, {y:.1f})" for nid, (x, y) in sorted(self.topology_map.items())])
        dl.info(f"[TOPOLOGY] Loaded {len(self.topology_map)} nodes: {topo_str}")
        
        self.sybil_detector.topology_map = self.topology_map
        
        # Inference Engine Logging (Debouncing)
        self.inference_logs = deque(maxlen=15)
        self.last_inf_key = None
        self.last_inf_count = 0
        
        self.packet_count = 0
        self.learning_duration_pkts = 250
        self.learning_finalized = False
        self.latest_temps = {}
        self.temp_history = {}
        
        # Attack Wave Awareness: track recent HIJACK/FDI blocks
        self.hijack_block_log = []  # list of timestamps when nodes were blocked for HIJACK
        
    def log_inference(self, inf_type, target_id, title, detail, color="#ffffff"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        inf_key = f"{inf_type}_{target_id}"
        
        if inf_key == self.last_inf_key:
            self.last_inf_count += 1
            # Update the last log with badge
            if len(self.inference_logs) > 0:
                last_log = self.inference_logs.pop()
                # Remove old badge if exists
                base_html = last_log.split('<span class="inf-badge">')[0]
                new_log = f'{base_html}<span class="inf-badge">Blocked {self.last_inf_count} more similar events</span>'
                self.inference_logs.append(new_log)
        else:
            self.last_inf_key = inf_key
            self.last_inf_count = 0
            
            icon = "fa-shield-alt"
            if inf_type == "BIPOLAR": icon = "fa-random"
            elif inf_type == "ZONE": icon = "fa-ban"
            elif inf_type == "FDI": icon = "fa-fire-extinguisher"
            
            html = f"""
            <div class="inf-entry" style="border-left-color: {color};">
                <div class="inf-header">
                    <span class="inf-time">[{ts}]</span>
                    <span class="inf-title" style="color: {color}"><i class="fas {icon}"></i> {title}</span>
                </div>
                <div class="inf-body">{detail}</div>
            </div>
            """
            self.inference_logs.append(html)
            dl.debug(f"INFERENCE [{inf_type}] Node {target_id}: {title} - {detail}")

    def log_event(self, msg):
        dl.debug(msg)


        
    def process_packet(self, node_id, rssi, temp_c):
        self.packet_count += 1
        is_learning = self.packet_count < self.learning_duration_pkts
        
        if is_learning:
            self.sybil_detector.learn(node_id, rssi)
            self.fdi_detector.check(temp_c)
            if node_id not in self.temp_history:
                self.temp_history[node_id] = deque(maxlen=10)
            self.temp_history[node_id].append(temp_c)
            return True
            
        if not self.learning_finalized:
            self.sybil_detector.finalize_learning()
            self.learning_finalized = True
            self.log_inference("SYS", 0, "SYSTEM ARMED", "Learning phase completed. RSSI Profiling database built. Security layers monitoring in real-time.", "#10b981")
            self.log_inference("SYS", 0, "Há»† THá»NG ÄÃƒ KÃCH HOáº T (ARMED)", "HoÃ n táº¥t giai Ä‘oáº¡n há»c (Learning). Cơ sở dữ liệu RSSI Profiling đã được xây dựng. CÃ¡c lá»›p báº£o máº­t Ä‘ang theo dÃµi thá»i gian thá»±c.", "#10b981")
            
        if self.trust_manager.is_blacklisted(node_id):
            return False
            
        self.latest_temps[node_id] = temp_c
        
        sybil_passed, sybil_reason, attack_type = self.sybil_detector.check(node_id, rssi)
        is_fake_id = (attack_type in ["ZONE_BLOCK", "SYBIL_CLONE"])
        
        # Restore ZONE_BLOCK triggering
        if attack_type == "SYBIL_CLONE":
            self.sybil_detector.record_rssi_violation(rssi)
            
        # === Spatial Cross-Verification for Spoofing (MISMATCH) ===
        if attack_type == "MISMATCH":
            hot_neighbors = []
            radius_m = 15.0
            if hasattr(self, 'topology_map') and node_id in self.topology_map:
                mx, my = self.topology_map[node_id]
                for nid, ntemp in self.latest_temps.items():
                    if nid != node_id and ntemp > 60.0 and nid in self.topology_map:
                        nx, ny = self.topology_map[nid]
                        dist = ((nx - mx)**2 + (ny - my)**2) ** 0.5
                        if dist <= radius_m:
                            hot_neighbors.append(nid)
            
            packet_hot = temp_c > 60.0
            neighbors_hot = len(hot_neighbors) > 0
            
            if packet_hot and not neighbors_hot:
                self.stats['spoof_blocked'] += 1
                self.log_inference("SPOOF", node_id, f"\u26d4 SPOOF BLOCKED: FALSE ALARM ({node_id})",
                                   f"<b>Analysis:</b> Protocol reports MISMATCH. Node {node_id} reports {temp_c:.1f}C but surroundings are normal.<br><b>Conclusion:</b> False Alarm Attack.<br><b>Action:</b> PACKET DROPPED. Trust UNCHANGED.", "#eab308")
                return False
                
            elif not packet_hot and neighbors_hot:
                self.stats['spoof_blocked'] += 1
                self.log_inference("SPOOF", node_id, f"\u26d4 SPOOF BLOCKED: FIRE SUPPRESSION ({node_id})",
                                   f"<b>Analysis:</b> Protocol reports MISMATCH. Area is ON FIRE but Node {node_id} reports {temp_c:.1f}C.<br><b>Conclusion:</b> Fire Suppression Attack.<br><b>Action:</b> PACKET DROPPED. Trust UNCHANGED.", "#eab308")
                return False
            
            # If it reaches here (Case 3 or 4), it's either Real Fire+Noise or Normal+Noise. 
            # We let it pass to fdi_passed check, and it will receive standard beta+4.0 penalty from TrustManager.

            
        fdi_passed = self.fdi_detector.check(temp_c)
        if fdi_passed:
            if not hasattr(self, 'last_normal_time'):
                self.last_normal_time = {}
            import time
            self.last_normal_time[node_id] = time.time()
        
        spatial_reason = ""
        if not fdi_passed and temp_c > 60.0:
            # === Fire Confirmation Protocol (Coordinate Map) ===
            import time
            
            if not hasattr(self, 'fire_timestamps'):
                self.fire_timestamps = {}
            if temp_c > 60.0 and node_id not in self.fire_timestamps:
                self.fire_timestamps[node_id] = time.time()
                
            hot_neighbors = []
            cold_neighbors = []
            radius_m = 15.0 # Inner ring
            outer_radius_m = 25.0 # Outer ring
            
            if node_id not in getattr(self, 'fire_warning_count', {}):
                if not hasattr(self, 'fire_warning_count'): self.fire_warning_count = {}
                self.fire_warning_count[node_id] = 0
            self.fire_warning_count[node_id] += 1
            
            # Scan coordinates
            if hasattr(self, 'topology_map') and node_id in self.topology_map:
                mx, my = self.topology_map[node_id]
                for nid, ntemp in self.latest_temps.items():
                    if nid != node_id and nid in self.topology_map:
                        if self.trust_manager.is_blacklisted(nid):
                            continue
                        nx, ny = self.topology_map[nid]
                        dist = math.hypot(mx - nx, my - ny)
                        if dist <= radius_m:
                            if ntemp > 60.0:
                                hot_neighbors.append((nid, dist))
                        elif dist <= outer_radius_m:
                            if ntemp < 40.0:
                                cold_neighbors.append((nid, dist))
            else:
                # Fallback: global scan if map is missing
                for nid, ntemp in self.latest_temps.items():
                    if nid != node_id and ntemp > 60.0:
                        hot_neighbors.append((nid, 0.0))
            
            observation_window = 6.0
            elapsed = 0.0
            if node_id in self.fire_timestamps:
                elapsed = time.time() - self.fire_timestamps[node_id]
                
            # --- Observation Mode (Khoa mom) ---
            if elapsed < observation_window:
                # Not enough time has passed to make a decision. Wait.
                fdi_passed = True # Temporarily pass to avoid blocking during observation
                spatial_reason = f"OBSERVING: Gathering data. Window closes in {observation_window - elapsed:.1f}s"
                if self.fire_warning_count[node_id] == 1:
                    self.log_inference("WARN", node_id, f"\U0001f50d OBSERVING CLUSTER: NODE {node_id}",
                                       f"<b>Analysis:</b> Node {node_id} reported {temp_c:.1f}C. Pausing decision to gather neighbor data for {observation_window}s.<br><b>Action:</b> System holds verdict.", "#fbbf24")
            else:
                # --- Observation Window Closed -> Final Judgment ---
                # 1. Spatio-Temporal Hijack Detection (Sync Burst & Temp Cliff)
                sync_nodes = []
                teleporting_nodes = []
                
                if node_id in self.fire_timestamps:
                    t_self = self.fire_timestamps[node_id]
                    
                    # Check hot neighbors for Sync Burst
                    for hn, _ in hot_neighbors:
                        if hn in self.fire_timestamps:
                            if abs(self.fire_timestamps[hn] - t_self) < 5.0:
                                sync_nodes.append(hn)
                                
                    # Check ALL nodes for Teleporting Fire (Global Spatial Anomaly)
                    if hasattr(self, 'topology_map') and node_id in self.topology_map:
                        mx, my = self.topology_map[node_id]
                        for other_id, t_other in self.fire_timestamps.items():
                            if other_id != node_id and abs(t_other - t_self) < 5.0:
                                if self.trust_manager.is_blacklisted(other_id):
                                    continue
                                ox, oy = self.topology_map.get(other_id, (mx, my))
                                dist = math.hypot(mx - ox, my - oy)
                                if dist > 35.0: # 35 meters -> definitely another cluster
                                    teleporting_nodes.append((other_id, dist))
                                    
                is_hijack = False
                hijack_reason = ""
                
                if len(teleporting_nodes) >= 1:
                    is_hijack = True
                    hijack_reason = f"Teleporting Fire! Simultaneous burst across clusters (>35m)."
                elif len(sync_nodes) >= 4: # At least 5 nodes (self + 4) sync
                    is_hijack = True
                    hijack_reason = f"Sync Burst! {len(sync_nodes)+1} nodes jumped >60C within 5s."
                elif len(hot_neighbors) >= 5 and len(cold_neighbors) >= 2:
                    is_hijack = True
                    hijack_reason = f"Temp Cliff! No gradient outside 15m cluster."

                if is_hijack:
                    fdi_passed = False
                    attack_type = "HIJACK"
                    spatial_reason = f"HIJACK DETECTED: {hijack_reason}"
                    self.hijack_block_log.append(time.time())
                    if not hasattr(self, 'hijack_alerted'): self.hijack_alerted = set()
                    if node_id not in self.hijack_alerted:
                        self.log_inference("FDI", node_id, f"\u2620 HIJACK DETECTED: NODE {node_id}",
                                           f"<b>Analysis:</b> After {observation_window}s window: {hijack_reason}<br><b>Conclusion:</b> Coordinated FDI Attack (Hijacked Cluster).<br><b>Action:</b> INSTANT BLOCK!", "#7f1d1d")
                        self.hijack_alerted.add(node_id)
                elif len(hot_neighbors) >= 1:
                    # --- Attack Wave Awareness ---
                    now_awa = time.time()
                    recent_hijack_blocks = sum(1 for t in self.hijack_block_log if now_awa - t < 120.0)
                    
                    # If active attack wave (>=3 HIJACK blocks in 2 min),
                    # require at least 1 innocent (non-suspect) hot neighbor
                    all_suspects = True
                    if recent_hijack_blocks >= 3:
                        for hn, _ in hot_neighbors:
                            if self.fire_warning_count.get(hn, 0) == 0:
                                all_suspects = False
                                break
                    else:
                        all_suspects = False
                    
                    if all_suspects and recent_hijack_blocks >= 3:
                        # COLLUSION: All hot neighbors are suspects during attack wave
                        fdi_passed = False
                        attack_type = "HIJACK"
                        suspect_ids = [str(n[0]) for n in hot_neighbors[:5]]
                        spatial_reason = f"COLLUSION DETECTED: All {len(hot_neighbors)} hot neighbors are suspects during attack wave ({recent_hijack_blocks} recent blocks)"
                        self.hijack_block_log.append(time.time())
                        if not hasattr(self, 'hijack_alerted'): self.hijack_alerted = set()
                        if node_id not in self.hijack_alerted:
                            self.log_inference("FDI", node_id, f"\u2620 COLLUSION DETECTED: NODE {node_id}",
                                               f"<b>Analysis:</b> After {observation_window}s window: Active attack wave ({recent_hijack_blocks} nodes blocked recently). Hot neighbors [{', '.join(suspect_ids)}] are ALL under fire observation.<br><b>Conclusion:</b> Mutual vouching between suspects. No innocent witness.<br><b>Action:</b> INSTANT BLOCK!", "#7f1d1d")
                            self.hijack_alerted.add(node_id)
                    else:
                        # Normal TRUE FIRE (no attack wave, or has innocent witnesses)
                        hot_ids = [str(n[0]) for n in hot_neighbors[:5]]
                        fdi_passed = True
                        spatial_reason = f"TRUE FIRE CONFIRMED: {len(hot_neighbors)+1} nodes within 15m report fire (Node {', '.join(hot_ids)})"
                        if not hasattr(self, 'true_fire_alerted'): self.true_fire_alerted = set()
                        if node_id not in self.true_fire_alerted:
                            self.log_inference("FIRE", node_id, f"\U0001f525 TRUE FIRE CONFIRMED: CLUSTER NODE {node_id}",
                                               f"<b>Analysis:</b> After {observation_window}s window: Nodes {', '.join(hot_ids)} within 15m of Node {node_id} also report >60C. Gradient is natural.<br><b>Conclusion:</b> Localized spatial event, TRUE FIRE! System MAINTAINS 100% Trust.<br><b>Action:</b> FIRE ALERT!", "#ff4500")
                            self.true_fire_alerted.add(node_id)
                else:
                    # No neighbors confirmed after observation window
                    spatial_reason = f"No nodes within 15m confirmed fire after {observation_window}s window"
                    fdi_passed = False
                    attack_type = "HIJACK" # Lone node reporting >60C without neighbors is a definite anomaly

        # === FDI Detection with Fire Confirmation ===
        if not fdi_passed and temp_c > 60.0 and not is_fake_id and node_id in self.sybil_detector.profile:
            self.stats['fdi_blocked'] += 1
            self.log_inference("FDI", node_id, f"CAPTURED NODE: NODE {node_id} SUSPECTED OF DATA FORGERY",
                               f"<b>Analysis:</b> Node {node_id} reports abnormal {temp_c:.1f}C. {spatial_reason}.<br><b>Conclusion:</b> No confirmation from neighbors. Node likely captured.<br><b>Action:</b> Trust deducted for Node {node_id}!", "#ea580c")

        blacklisted = self.trust_manager.update_trust(node_id, sybil_passed, fdi_passed, attack_type)
        if blacklisted:
            self.log_inference("BLACKLIST", node_id, f"NODE EXILED: NODE {node_id} BLACKLISTED", 
                               f"Trust Score fell below 40%. Completely isolated Node {node_id} from network.", "#ef4444")
            return False
            
        return True

    def get_ui_data(self):
        ui_trust = {}
        safe_count = 0
        warn_count = 0
        blocked_count = 0
        
        for nid, rec in self.trust_manager.trust_db.items():
            trust_val = (rec['alpha'] / (rec['alpha'] + rec['beta'])) * 100.0
            if rec['blacklisted']:
                blocked_count += 1
            elif trust_val >= 80:
                safe_count += 1
            else:
                warn_count += 1
                
            ui_trust[str(nid)] = {
                'score': round(trust_val, 1),
                'blacklisted': rec['blacklisted']
            }
            
        # Format RSSI Blacklist Zones
        zones = []
        for bl in self.sybil_detector.rssi_blacklist:
            zones.append(f"[{bl-2.0} to {bl+2.0} dBm]")
            
        return {
            'trust_db': ui_trust, 
            'inference_logs': list(self.inference_logs),
            'learning_pkts_left': max(0, self.learning_duration_pkts - self.packet_count),
            'learning_pkts_total': self.learning_duration_pkts,
            'is_armed': self.learning_finalized,
            'rssi_zones': zones,
            'node_stats': {
                'safe': safe_count,
                'warn': warn_count,
                'blocked': blocked_count
            },
            'attack_stats': self.stats
        }
