"""
collect_training_data.py
====================
Parse log Contiki-NG/Cooja (dinh dang: "<time> ID:<node> [LEVEL: MODULE] message")
va trich xuat bang feature theo cua so thoi gian (windowed features) de train ML
phat hien vampire attack (RPL Version Number Attack) trong WSN.
"""
import argparse
import glob
import os
import re
from pathlib import Path
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# 1) REGEX cho dinh dang log Contiki-NG (dieu chinh neu ban them cac dong log khac)
# ----------------------------------------------------------------------------
LOG_LINE_RE = re.compile(
    r'^(?P<time>\d+)\s+ID:(?P<node>\d+)\s+\[(?P<level>\w+)\s*:\s*(?P<module>[^\]]+?)\s*\]\s?(?P<msg>.*)$'
)
RE_SINK_RX = re.compile(
    r'RX sink=(?P<sink>\d+) cluster=(?P<cluster>\d+) node=(?P<origin>\d+) seq=(?P<seq>\d+) '
    r'energy_mj=(?P<energy_mj>\d+) temp_c=(?P<temp_c>[\d.]+) bytes=(?P<bytes>\d+) latency_ms=(?P<latency_ms>\d+)'
)
RE_NODE_TX = re.compile(
    r'TX cluster=(?P<cluster>\d+) node=(?P<origin>\d+) seq=(?P<seq>\d+) energy_mj=(?P<energy_mj>\d+) bytes=(?P<bytes>\d+)'
)
RE_DIO_RECV = re.compile(
    r'received a (?:multicast|unicast)-DIO from [^,]+, instance_id \d+, DAG ID [^,]+, '
    r'version (?P<version>\d+), dtsn \d+, rank (?P<rank_peer>\d+)'
)
RE_NBR_STATE = re.compile(
    r'nbr: own state, addr [^,]+, DAG state: \w+, MOP \d+ OCP \d+ rank (?P<rank>\d+) '
    r'max-rank \d+, dioint (?P<dioint>\d+), nbr count (?P<nbrcount>\d+) \((?P<reason>[^)]+)\)'
)

# Neu Cooja/board cua ban dung don vi timestamp khac, chinh lai o day.
# Voi log mau: dong dau ~26000, dong cuoi ~1.34e9 -> phu hop voi don vi MICROGIAY (us).
TIME_UNIT_PER_SEC = 1_000_000
WINDOW_SEC = 60          # do rong cua so thoi gian de gom feature (giay, dong bo voi 60s tren Contiki-NG)
AFTERMATH_SEC = 15       # chi dung khi KHONG co scenario baseline rieng (xem ham label_attack_windows)


def parse_log(path: str) -> pd.DataFrame:
    """Doc file log tho, tra ve DataFrame moi dong 1 ban ghi (time, node, level, module, msg)."""
    rows = []
    with open(path, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            m = LOG_LINE_RE.match(line)
            if m:
                rows.append(m.groupdict())
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Khong parse duoc dong nao trong {path} - kiem tra lai dinh dang log / regex LOG_LINE_RE")
    df['time'] = df['time'].astype(np.int64)
    df['node'] = df['node'].astype(int)
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Them cac cot co/khong (boolean) va cac truong so duoc trich xuat tu tung loai message."""
    df = df.copy()
    df['is_dio_send'] = df['msg'].str.startswith('sending a multicast-DIO') | df['msg'].str.startswith('sending a unicast-DIO')
    df['is_dio_recv'] = df['msg'].str.startswith('received a multicast-DIO') | df['msg'].str.startswith('received a unicast-DIO')
    df['is_dao_send'] = df['msg'].str.startswith('sending a DAO')
    df['is_dao_recv'] = df['msg'].str.startswith('received a DAO')
    df['is_dis_send'] = df['msg'].str.startswith('sending a DIS')
    df['is_global_repair'] = df['msg'].str.contains('global repair', regex=False)
    df['is_local_repair'] = df['msg'].str.contains('local repair', regex=False)
    df['is_parent_switch'] = df['msg'].str.startswith('parent switch:')
    df['is_queue_flush'] = df['msg'].str.contains('flushing packet', regex=False)
    df['is_not_assoc'] = df['msg'].str.contains('not associated', regex=False)
    df['is_vna_trigger'] = df['msg'].str.contains('ATTACK_VNA: Triggered', regex=False)  # CHI de danh nhan / debug
    
    # Detect coordinated attack phases and actions from tags
    df['attack_phase'] = df['msg'].str.extract(r'TAG:PHASE=(\w+)', expand=False)
    df['attack_action'] = df['msg'].str.extract(r'TAG:ACTION=(\w+)', expand=False)

    df = pd.concat([df, df['msg'].str.extract(RE_SINK_RX).add_prefix('sinkrx_')], axis=1)
    df = pd.concat([df, df['msg'].str.extract(RE_NODE_TX).add_prefix('tx_')], axis=1)
    df = pd.concat([df, df['msg'].str.extract(RE_DIO_RECV)], axis=1)
    df = pd.concat([df, df['msg'].str.extract(RE_NBR_STATE)], axis=1)
    return df


def determine_attacker_nodes(scenario: str, logfile: str = '', df: pd.DataFrame = None, override=None) -> list:
    """Xac dinh danh sach cac node tan cong (ground truth) theo kich ban:
    - normal: khong co attacker ([]).
    - coordinated: [29, 30, 31].
    - carousel / stretch / stealth / vampire: [29].
    """
    if override is not None:
        return sorted(list(set(override)))

    scenario_lower = (scenario or '').lower().strip()
    logfile_lower = (logfile or '').lower().replace('\\', '/')

    # 1. Kich ban normal: TUYET DOI khong co node tan cong
    if scenario_lower == 'normal' or 'normal' in logfile_lower:
        return []

    # 2. Kich ban coordinated attack: 3 node tan cong 29, 30, 31
    if 'coordinated' in scenario_lower or 'coordinated' in logfile_lower:
        return [29, 30, 31]

    if df is not None and not df.empty and 'msg' in df.columns:
        if df['msg'].str.contains('COORDINATED', case=False, na=False).any():
            return [29, 30, 31]

    # 3. Cac kich ban con lai (carousel, stretch, stealth, vampire mac dinh): chi co node 29
    return [29]


def build_node_window_features(df: pd.DataFrame, window_sec=WINDOW_SEC, time_unit_per_sec=TIME_UNIT_PER_SEC,
                               attacker_nodes_override=None, scenario='vampire', logfile=''):
    """Feature theo tung (node, cua_so_thoi_gian). Dung de: phat hien + KHOANH VUNG node nghi van."""
    win = window_sec * time_unit_per_sec
    df = df.copy()
    df['window'] = (df['time'] // win).astype(int)
    all_nodes = sorted(df['node'].unique())
    n_windows = int(df['window'].max()) + 1
    idx = pd.MultiIndex.from_product([all_nodes, range(n_windows)], names=['node', 'window'])
    feat = pd.DataFrame(index=idx)

    count_specs = [
        ('is_dio_send', 'dio_tx_count'), ('is_dio_recv', 'dio_rx_count'),
        ('is_dao_send', 'dao_tx_count'), ('is_dao_recv', 'dao_rx_count'),
        ('is_dis_send', 'dis_tx_count'), ('is_global_repair', 'global_repair_count'),
        ('is_local_repair', 'local_repair_count'), ('is_parent_switch', 'parent_switch_count'),
        ('is_queue_flush', 'queue_flush_count'), ('is_not_assoc', 'not_assoc_count'),
    ]
    for col, name in count_specs:
        feat[name] = df[df[col]].groupby(['node', 'window']).size().reindex(idx, fill_value=0)

    # So phien ban (version) DIO KHAC NHAU ma node nay nghe duoc trong 1 cua so
    # -> dau hieu RAT MANH cho Version Number Attack (binh thuong phai luon = 1 khi da on dinh)
    dio_recv_rows = df[df['is_dio_recv']]
    feat['distinct_dio_versions_seen'] = dio_recv_rows.groupby(['node', 'window'])['version'].nunique().reindex(idx, fill_value=0)
    # DIO "poison" (rank_peer = 65535/INFINITE_RANK): hang xom bao "dung dung toi lam parent nua"
    # -> tang manh khi mang dang global-repair lien tuc
    poison = dio_recv_rows[dio_recv_rows['rank_peer'].astype(float) == 65535]
    feat['poison_dio_recv_count'] = poison.groupby(['node', 'window']).size().reindex(idx, fill_value=0)

    # Trang thai RPL cua chinh node (tu cac dong "nbr: own state ...")
    # LUU Y QUAN TRONG: RPL dung rank = 65535 (0xFFFF = INFINITE_RANK) nhu mot gia tri "sentinel"
    # (node chua join DAG / dang bi "poison" trong luc repair) - KHONG phai rank that.
    # Neu khong loc ra, 1 dong rank=65535 se lam std/mean bi vo nghia (outlier khong lo).
    # Nhung ban than viec "bao nhieu lan roi vao trang thai infinite-rank" lai la 1 FEATURE TOT
    # vi no tang len ro ret khi node bi buoc roi DAG lien tuc do tan cong version number.
    INFINITE_RANK = 65535
    nbr_rows = df[df['reason'].notna()].copy()
    for c in ['rank', 'dioint', 'nbrcount']:
        nbr_rows[c] = nbr_rows[c].astype(float)
    nbr_rows['rank_is_infinite'] = nbr_rows['rank'] == INFINITE_RANK
    nbr_rows.loc[nbr_rows['rank_is_infinite'], 'rank'] = np.nan
    nbr_rows = nbr_rows.sort_values('time')
    g_last = nbr_rows.groupby(['node', 'window']).last()
    feat['rank_last'] = g_last['rank'].reindex(idx)
    feat['dioint_last'] = g_last['dioint'].reindex(idx)          # dioint nho = trickle timer bi reset lien tuc
    feat['nbrcount_last'] = g_last['nbrcount'].reindex(idx)
    feat['rank_std'] = nbr_rows.groupby(['node', 'window'])['rank'].std().reindex(idx)  # de NaN neu <2 mau, KHONG ep ve 0
    feat['infinite_rank_count'] = nbr_rows.groupby(['node', 'window'])['rank_is_infinite'].sum().reindex(idx, fill_value=0)

    # Nang luong: phai TINH HIEU giua cac lan doc lien tiep (delta), KHONG lay max-min TRONG 1 cua so
    # (vi thuong moi cua so chi co 1 lan TX -> max-min se luon = 0, day la loi rat de mac phai)
    tx_rows = df[df['tx_energy_mj'].notna()][['time', 'window', 'node', 'tx_energy_mj']].copy()
    tx_rows['tx_energy_mj'] = tx_rows['tx_energy_mj'].astype(float)
    tx_rows = tx_rows.sort_values(['node', 'time'])
    tx_rows['prev_energy'] = tx_rows.groupby('node')['tx_energy_mj'].shift(1)
    tx_rows['prev_time'] = tx_rows.groupby('node')['time'].shift(1)
    tx_rows['energy_used'] = tx_rows['prev_energy'] - tx_rows['tx_energy_mj']
    tx_rows['dt_sec'] = (tx_rows['time'] - tx_rows['prev_time']) / time_unit_per_sec
    tx_rows['energy_rate_mj_per_s'] = tx_rows['energy_used'] / tx_rows['dt_sec']

    feat['tx_count'] = tx_rows.groupby(['node', 'window']).size().reindex(idx, fill_value=0)
    feat['energy_used_sum'] = tx_rows.groupby(['node', 'window'])['energy_used'].sum().reindex(idx)
    feat['energy_rate_mj_per_s_mean'] = tx_rows.groupby(['node', 'window'])['energy_rate_mj_per_s'].mean().reindex(idx)

    # Goi tin den duoc sink (gan cho node NGUON, khong phai ID cua sink)
    rx_rows = df[df['sinkrx_origin'].notna()][['window', 'sinkrx_origin', 'sinkrx_latency_ms']].copy()
    rx_rows.rename(columns={'sinkrx_origin': 'node'}, inplace=True)
    rx_rows['node'] = rx_rows['node'].astype(int)
    rx_rows['sinkrx_latency_ms'] = rx_rows['sinkrx_latency_ms'].astype(float)
    feat['delivered_count'] = rx_rows.groupby(['node', 'window']).size().reindex(idx, fill_value=0)
    feat['avg_latency_ms'] = rx_rows.groupby(['node', 'window'])['sinkrx_latency_ms'].mean().reindex(idx)

    # -------------------------------------------------------------------------
    # LOCAL EMBEDDED FEATURES (observable on-board by a sensor node in Contiki-NG)
    # -------------------------------------------------------------------------
    # 1. dio_rate: Number of DIOs transmitted/observed in the window (normalized to 60s)
    feat['dio_rate'] = feat['dio_tx_count']
    # If a node only receives DIOs, dio_rx_count can also serve as observation:
    feat['dio_rate'] = feat['dio_rate'].fillna(0).astype(int)

    # 2. version_delta: Discrepancy in RPL DAG versions
    # In normal operation, DAG version is constant. In Vampire (version attack), version jumps.
    if 'distinct_dio_versions_seen' in feat.columns:
        feat['version_delta'] = (feat['distinct_dio_versions_seen'] - 1).clip(lower=0)
    else:
        feat['version_delta'] = 0

    # 3. rank: Advertised RPL rank (normal range ~128 - 2000, 65535 is infinite)
    feat['rank'] = feat['rank_last'].fillna(1000).astype(int)

    # 4. rank_delta: Magnitude of rank fluctuation / sudden changes
    rank_diff = feat.groupby(level='node')['rank'].diff().abs()
    feat['rank_delta'] = rank_diff.fillna(feat['rank_std'].fillna(0)).astype(int)

    # 5. is_poison: Node advertised or received infinite rank (sentinel for DAG repair/poisoning)
    feat['is_poison'] = ((feat['infinite_rank_count'] > 0) | (feat['poison_dio_recv_count'] > 0)).astype(int)

    # ----- CHI DE LAM GROUND-TRUTH / DEBUG, KHONG DUA VAO FEATURE X KHI TRAIN -----
    all_attackers = determine_attacker_nodes(
        scenario=scenario, logfile=logfile, df=df, override=attacker_nodes_override
    )
    feat['is_attacker_node_GROUNDTRUTH'] = feat.index.get_level_values('node').isin(all_attackers).astype(int)
    
    # Add attack type information for each node-window
    if not all_attackers or (scenario and scenario.lower() == 'normal'):
        feat['attack_type_GROUNDTRUTH'] = 'NONE'
    else:
        sc_lower = (scenario or '').lower()
        lf_lower = (logfile or '').lower().replace('\\', '/')
        if 'coordinated' in sc_lower or 'coordinated' in lf_lower:
            atk_type = 'COORDINATED'
        elif 'carousel' in sc_lower or 'carousel' in lf_lower:
            atk_type = 'CAROUSEL'
        elif 'stretch' in sc_lower or 'stretch' in lf_lower:
            atk_type = 'STRETCH'
        elif 'stealth' in sc_lower or 'stealth' in lf_lower:
            atk_type = 'STEALTH'
        else:
            atk_type = 'VAMPIRE'

        feat['attack_type_GROUNDTRUTH'] = 'NONE'
        feat.loc[feat['is_attacker_node_GROUNDTRUTH'] == 1, 'attack_type_GROUNDTRUTH'] = atk_type

    # For coordinated attacks: track phase distribution in each window
    phase_rows = df.loc[df['attack_phase'].notna()]
    if not phase_rows.empty and 'COORDINATED' in feat['attack_type_GROUNDTRUTH'].values:
        phase_counts = phase_rows.groupby(['node', 'window', 'attack_phase']).size().unstack(fill_value=0)
        for phase in ['CAROUSEL', 'STRETCH', 'IDLE']:
            col_name = f'phase_{phase.lower()}_count_GROUNDTRUTH'
            if phase in phase_counts.columns:
                feat[col_name] = phase_counts[phase].reindex(idx, fill_value=0)
            else:
                feat[col_name] = 0
    else:
        for phase in ['carousel', 'stretch', 'idle']:
            feat[f'phase_{phase}_count_GROUNDTRUTH'] = 0

    # Track attack actions
    action_rows = df.loc[df['attack_action'].notna()]
    if not action_rows.empty and all_attackers:
        for action in ['VERSION_MANIP', 'RANK_MANIP']:
            action_count = action_rows[action_rows['attack_action'] == action].groupby(['node', 'window']).size()
            feat[f'action_{action.lower()}_count_GROUNDTRUTH'] = action_count.reindex(idx, fill_value=0)
    else:
        for action in ['version_manip', 'rank_manip']:
            feat[f'action_{action}_count_GROUNDTRUTH'] = 0

    return feat.reset_index(), all_attackers


def build_network_window_features(df: pd.DataFrame, window_sec=WINDOW_SEC, time_unit_per_sec=TIME_UNIT_PER_SEC):
    """Feature gop toan mang theo cua so thoi gian. Dung de phat hien 'mang co dang bi tan cong khong'
    o muc giam sat trung tam (sink / border router / monitor server) - khong can biet node nao."""
    win = window_sec * time_unit_per_sec
    df = df.copy()
    df['window'] = (df['time'] // win).astype(int)
    n_windows = int(df['window'].max()) + 1
    idx = pd.Index(range(n_windows), name='window')
    feat = pd.DataFrame(index=idx)

    count_specs = [
        ('is_dio_send', 'total_dio_tx'), ('is_dio_recv', 'total_dio_rx'),
        ('is_dao_send', 'total_dao_tx'), ('is_dao_recv', 'total_dao_rx'),
        ('is_dis_send', 'total_dis_tx'), ('is_global_repair', 'total_global_repair'),
        ('is_local_repair', 'total_local_repair'), ('is_parent_switch', 'total_parent_switch'),
        ('is_queue_flush', 'total_queue_flush'), ('is_not_assoc', 'total_not_assoc'),
    ]
    for col, name in count_specs:
        feat[name] = df[df[col]].groupby('window').size().reindex(idx, fill_value=0)

    feat['distinct_dio_versions_network'] = df[df['is_dio_recv']].groupby('window')['version'].nunique().reindex(idx, fill_value=0)

    tx_rows = df[df['tx_energy_mj'].notna()].copy()
    feat['n_nodes_active'] = tx_rows.groupby('window')['node'].nunique().reindex(idx, fill_value=0)
    feat['total_tx_count'] = tx_rows.groupby('window').size().reindex(idx, fill_value=0)

    rx_rows = df[df['sinkrx_origin'].notna()].copy()
    rx_rows['sinkrx_latency_ms'] = rx_rows['sinkrx_latency_ms'].astype(float)
    feat['total_delivered'] = rx_rows.groupby('window').size().reindex(idx, fill_value=0)
    feat['avg_latency_ms_network'] = rx_rows.groupby('window')['sinkrx_latency_ms'].mean().reindex(idx)
    feat['pdr_window'] = feat['total_delivered'] / feat['total_tx_count'].replace(0, np.nan)

    return feat.reset_index()


def label_attack_windows(net_feat, trigger_times, window_sec=WINDOW_SEC, time_unit_per_sec=TIME_UNIT_PER_SEC, aftermath_sec=AFTERMATH_SEC):
    """CACH GAN NHAN 'CHUA' khi ban chi co DUY NHAT 1 file log chua ca giai doan tan cong.
    >>> CACH TOT HON (khuyen nghi): chay wsn-2sink-full.csc (khong co node tan cong) rieng,
    roi gan scenario='normal' cho toan bo file do (xem ham load_scenario ben duoi). <<<
    """
    win = window_sec * time_unit_per_sec
    trigger_windows = sorted(set((np.array(trigger_times) // win).astype(int)))
    aftermath_windows = int(np.ceil(aftermath_sec / window_sec))
    labeled = set()
    for w in trigger_windows:
        for k in range(aftermath_windows + 1):
            labeled.add(w + k)
    net_feat = net_feat.copy()
    net_feat['label_attack'] = net_feat['window'].isin(labeled).astype(int)
    return net_feat


def load_scenario(path: str, scenario: str, run_id: str, window_sec=WINDOW_SEC):
    """Diem mo rong: goi ham nay 1 lan cho MOI file log (moi lan chay Cooja / moi seed / moi kich ban),
    roi pd.concat() tat ca lai truoc khi train. `run_id` dung de split train/test theo NHOM (GroupKFold)
    de tranh leakage giua cac cua so cung 1 lan chay."""
    df = parse_log(path)
    df = enrich(df)
    node_feat, attackers = build_node_window_features(
        df, window_sec=window_sec, scenario=scenario, logfile=path
    )
    node_feat['scenario'] = scenario          # 'normal' | 'sybil' | 'vampire' ...
    node_feat['run_id'] = run_id              # vd: ten file, hoac seed
    node_feat['label_network_attack'] = 0 if scenario == 'normal' else 1
    return node_feat


if __name__ == '__main__':
    import os
    from pathlib import Path

    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Vi du su dung:
  # Trich xuat log binh thuong (5 file):
  python ml/collect_training_data.py data/logs/normal/run_1.log --scenario normal
  python ml/collect_training_data.py data/logs/normal/run_2.log --scenario normal

  # Trich xuat log co tan cong:
  python ml/collect_training_data.py data/logs/vampire/run_1.log --scenario vampire

  # Ket qua tu dong luu vao data/results/:
  #   data/results/features_normal_run_1_node.csv
  #   data/results/features_normal_run_1_network.csv
  #   data/results/features_vampire_run_1_node.csv
  #   ...

  # Sau do chay train:
  python ml/train_and_export.py
        """
    )
    ap.add_argument('logfile', help="Duong dan file log, thu muc chua log, hoac glob pattern (vd: ../dataset/coordinated/ hoac run_1.log)")
    ap.add_argument('--scenario', default='normal',
                    help="'normal' | 'vampire' | 'sybil' | 'carousel' | 'stretch' | 'stealth' | 'coordinated'")
    ap.add_argument('--run-id', default=None,
                    help="ID cua run (mac dinh: tu dong lay tu ten file)")
    ap.add_argument('--window-sec', type=int, default=WINDOW_SEC)
    ap.add_argument('--attacker-nodes', default=None,
                    help="Danh sach node id tan cong, cach nhau boi dau phay (vd: 29,30,31,32)")
    ap.add_argument('--split-runs', action='store_true',
                    help="Luu tach rieng tung file theo run (mac dinh: tu dong gom chung vao features_{scenario}_node.csv)")
    ap.add_argument('--out-dir', default='data/results',
                    help="Thu muc luu ket qua CSV (mac dinh: data/results/)")
    ap.add_argument('--out-node', default=None,
                    help="Ten file CSV node-level (mac dinh: tu dong gom theo scenario)")
    ap.add_argument('--out-network', default=None,
                    help="Ten file CSV network-level (mac dinh: tu dong gom theo scenario)")
    args = ap.parse_args()

    override_attackers = None
    if args.attacker_nodes:
        override_attackers = [int(x.strip()) for x in args.attacker_nodes.split(',') if x.strip()]

    os.makedirs(args.out_dir, exist_ok=True)

    # --- Tim danh sach file log can xu ly (ho tro thu muc, glob pattern, file le) ---
    p = Path(args.logfile)
    if p.is_dir():
        target_files = sorted(glob.glob(os.path.join(str(p), '*.log')))
    elif any(ch in args.logfile for ch in ['*', '?']):
        target_files = sorted(glob.glob(args.logfile))
    else:
        target_files = [args.logfile]

    if not target_files:
        print(f"LOI: Khong tim thay file log nao khop voi '{args.logfile}'")
        sys.exit(1)

    # --- Dat ten file output (mac dinh gom chung theo scenario) ---
    if args.out_node is None:
        if args.split_runs and len(target_files) == 1:
            run_tag = args.run_id or Path(target_files[0]).stem
            args.out_node = os.path.join(args.out_dir, f"features_{args.scenario}_{run_tag}_node.csv")
        else:
            args.out_node = os.path.join(args.out_dir, f"features_{args.scenario}_node.csv")

    if args.out_network is None:
        if args.split_runs and len(target_files) == 1:
            run_tag = args.run_id or Path(target_files[0]).stem
            args.out_network = os.path.join(args.out_dir, f"features_{args.scenario}_{run_tag}_network.csv")
        else:
            args.out_network = os.path.join(args.out_dir, f"features_{args.scenario}_network.csv")

    print(f"{'='*60}")
    print(f"TRICH XUAT & GOM FEATURES TU LOG")
    print(f"{'='*60}")
    print(f"  Target       : {args.logfile} ({len(target_files)} file(s))")
    print(f"  Scenario     : {args.scenario}")
    print(f"  Window       : {args.window_sec}s")
    print(f"  Output Node  : {args.out_node}")
    print(f"  Output Net   : {args.out_network}")
    print(f"{'='*60}")

    all_node_dfs = []
    all_net_dfs = []
    total_parsed_lines = 0

    for current_file in target_files:
        current_run_id = Path(current_file).stem if args.run_id is None or len(target_files) > 1 else args.run_id
        print(f"\n>> Dang xu ly: {os.path.basename(current_file)} (run_id: {current_run_id})...")

        df = parse_log(current_file)
        df = enrich(df)
        total_parsed_lines += len(df)

        node_feat, attackers = build_node_window_features(
            df,
            window_sec=args.window_sec,
            attacker_nodes_override=override_attackers,
            scenario=args.scenario,
            logfile=current_file
        )
        node_feat['scenario'] = args.scenario
        node_feat['run_id'] = current_run_id
        node_feat['log_file'] = os.path.basename(current_file)

        net_feat = build_network_window_features(df, window_sec=args.window_sec)
        net_feat['scenario'] = args.scenario
        net_feat['run_id'] = current_run_id
        net_feat['log_file'] = os.path.basename(current_file)

        if args.scenario.lower() == 'normal' or 'normal' in str(current_file).lower():
            net_feat['label_attack'] = 0
            node_feat['label_network_attack'] = 0
        else:
            trigger_times = df.loc[df['is_vna_trigger'], 'time'].tolist()
            if trigger_times:
                net_feat = label_attack_windows(net_feat, trigger_times, window_sec=args.window_sec)
            else:
                net_feat['label_attack'] = 1
            node_feat['label_network_attack'] = 1

        all_node_dfs.append(node_feat)
        all_net_dfs.append(net_feat)
        print(f"   -> {len(node_feat)} node windows, {len(net_feat)} net windows, Attackers: {attackers}")

    # Gom cac dataframe lai
    new_node_df = pd.concat(all_node_dfs, ignore_index=True)
    new_net_df = pd.concat(all_net_dfs, ignore_index=True)

    # Tu dong merge neu file da ton tai (ghi de cac run cu de tranh duplicate)
    if not args.split_runs and os.path.exists(args.out_node):
        try:
            old_node_df = pd.read_csv(args.out_node)
            incoming_runs = new_node_df['run_id'].unique()
            if 'run_id' in old_node_df.columns:
                old_node_df = old_node_df[~old_node_df['run_id'].isin(incoming_runs)]
            final_node_df = pd.concat([old_node_df, new_node_df], ignore_index=True)
        except Exception:
            final_node_df = new_node_df
    else:
        final_node_df = new_node_df

    if not args.split_runs and os.path.exists(args.out_network):
        try:
            old_net_df = pd.read_csv(args.out_network)
            incoming_runs = new_net_df['run_id'].unique()
            if 'run_id' in old_net_df.columns:
                old_net_df = old_net_df[~old_net_df['run_id'].isin(incoming_runs)]
            final_net_df = pd.concat([old_net_df, new_net_df], ignore_index=True)
        except Exception:
            final_net_df = new_net_df
    else:
        final_net_df = new_net_df

    # --- Luu CSV ---
    final_node_df.to_csv(args.out_node, index=False)
    final_net_df.to_csv(args.out_network, index=False)

    print(f"\n{'='*60}")
    print(f"HOAN THANH!")
    print(f"{'='*60}")
    print(f"  {total_parsed_lines:,} dong log da parse tu {len(target_files)} file")
    print(f"  {final_node_df.shape[0]:,} dong feature node-level trong: {args.out_node}")
    print(f"  {final_net_df.shape[0]:,} dong feature network-level trong: {args.out_network}")
    if 'run_id' in final_node_df.columns:
        print(f"  Cac run da gom ({final_node_df['run_id'].nunique()} runs): {sorted(final_node_df['run_id'].unique())}")
    if 'is_attacker_node_GROUNDTRUTH' in final_node_df.columns:
        dist_node = final_node_df['is_attacker_node_GROUNDTRUTH'].value_counts().to_dict()
        print(f"  Node labels: {dist_node}")
    print(f"{'='*60}")