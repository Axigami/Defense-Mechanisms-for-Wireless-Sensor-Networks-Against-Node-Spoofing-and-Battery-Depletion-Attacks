"""
collect_training_data.py
====================
Parse log Contiki-NG/Cooja (dinh dang: "<time> ID:<node> [LEVEL: MODULE] message")
va trich xuat bang feature theo cua so thoi gian (windowed features) de train ML
phat hien vampire attack (RPL Version Number Attack) trong WSN.

CACH DUNG NHANH:
    python3 extract_features.py data/logs/run_vampire.log --scenario vampire --out features_vampire.csv
    python3 extract_features.py data/logs/run_baseline.log --scenario normal --out features_normal.csv
    # roi gop nhieu file features_*.csv lai (pd.concat) truoc khi train

QUAN TRONG - TRANH DATA LEAKAGE:
    Cot ket thuc bang "_GROUNDTRUTH" (vi du is_attacker_node_GROUNDTRUTH) CHI dung de:
      (1) kiem tra / debug, (2) xay dung nhan (label) khi ban KHONG chay rieng scenario baseline.
    TUYET DOI KHONG dua cac cot nay vao tap feature X khi train model — vi mot he thong
    phat hien that ngoai doi KHONG the biet truoc "node nao la ke tan cong" (do la thu no
    dang can du doan!). Neu dua vao X, model se "ăn gian" va khong generalize duoc.
"""
import argparse
import re
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
WINDOW_SEC = 10          # do rong cua so thoi gian de gom feature (giay)
AFTERMATH_SEC = 5        # chi dung khi KHONG co scenario baseline rieng (xem ham label_attack_windows)


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

    df = pd.concat([df, df['msg'].str.extract(RE_SINK_RX).add_prefix('sinkrx_')], axis=1)
    df = pd.concat([df, df['msg'].str.extract(RE_NODE_TX).add_prefix('tx_')], axis=1)
    df = pd.concat([df, df['msg'].str.extract(RE_DIO_RECV)], axis=1)
    df = pd.concat([df, df['msg'].str.extract(RE_NBR_STATE)], axis=1)
    return df


def build_node_window_features(df: pd.DataFrame, window_sec=WINDOW_SEC, time_unit_per_sec=TIME_UNIT_PER_SEC):
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

    # ----- CHI DE LAM GROUND-TRUTH / DEBUG, KHONG DUA VAO FEATURE X KHI TRAIN -----
    # Identify attacker nodes by their log module
    # Attack modules: VAMPIRE, CAROUSEL, STRETCH, HYBRID, STEALTH
    attack_modules = ['VAMPIRE', 'CAROUSEL', 'STRETCH', 'HYBRID', 'STEALTH']
    attacker_nodes = df.loc[df['module'].isin(attack_modules), 'node'].unique().tolist()
    feat['is_attacker_node_GROUNDTRUTH'] = feat.index.get_level_values('node').isin(attacker_nodes).astype(int)

    return feat.reset_index(), attacker_nodes


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
    node_feat, attackers = build_node_window_features(df, window_sec=window_sec)
    node_feat['scenario'] = scenario          # 'normal' | 'sybil' | 'vampire' ...
    node_feat['run_id'] = run_id              # vd: ten file, hoac seed
    node_feat['label_network_attack'] = 0 if scenario == 'normal' else 1
    return node_feat


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('logfile')
    ap.add_argument('--scenario', default='vampire', help="'normal' | 'sybil' | 'vampire' (dat theo kich ban Cooja ban chay)")
    ap.add_argument('--run-id', default='run1')
    ap.add_argument('--window-sec', type=int, default=WINDOW_SEC)
    ap.add_argument('--out-node', default='features_node_level.csv')
    ap.add_argument('--out-network', default='features_network_level.csv')
    args = ap.parse_args()

    df = parse_log(args.logfile)
    df = enrich(df)

    node_feat, attackers = build_node_window_features(df, window_sec=args.window_sec)
    node_feat['scenario'] = args.scenario
    node_feat['run_id'] = args.run_id

    net_feat = build_network_window_features(df, window_sec=args.window_sec)
    if args.scenario == 'normal':
        net_feat['label_attack'] = 0
    else:
        trigger_times = df.loc[df['is_vna_trigger'], 'time'].tolist()
        if trigger_times:
            net_feat = label_attack_windows(net_feat, trigger_times, window_sec=args.window_sec)
        else:
            net_feat['label_attack'] = 1  # ca file la kich ban tan cong nhung khong co dong VAMPIRE de doi chieu

    node_feat.to_csv(args.out_node, index=False)
    net_feat.to_csv(args.out_network, index=False)

    print(f"[OK] {len(df)} dong log -> {node_feat.shape[0]} dong feature theo node, {net_feat.shape[0]} dong feature theo mang")
    print(f"[OK] Node bi danh dau la ke tan cong (ground-truth, chi de kiem tra): {attackers}")
    print(f"[OK] Da luu: {args.out_node}, {args.out_network}")
    if 'label_attack' in net_feat.columns:
        print(f"[OK] Phan bo nhan (network-level): {net_feat['label_attack'].value_counts().to_dict()}")