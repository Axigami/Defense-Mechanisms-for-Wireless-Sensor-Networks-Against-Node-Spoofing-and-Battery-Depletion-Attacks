# analyze_full.py
import re, sys
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns

# Cấu hình matplotlib để hiển thị tiếng Việt
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
sns.set_palette("husl")

PATTERNS = {
  'gen':    re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*GEN cluster=(?P<cl>\d+) node=(?P<node>\d+) gen_count=(?P<gc>\d+)'),
  'tx':     re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*TX cluster=(?P<cl>\d+) node=(?P<node>\d+) seq=(?P<seq>\d+) energy_mj=(?P<e>\d+) bytes=(?P<b>\d+)'),
  'txfail': re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*TXFAIL cluster=(?P<cl>\d+) node=(?P<node>\d+) gen_count=(?P<gc>\d+)'),
  'dead':   re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*DEAD cluster=(?P<cl>\d+) node=(?P<node>\d+) time_alive_s=(?P<alive>\d+) last_seq=(?P<seq>\d+) total_gen=(?P<gen>\d+) total_sent=(?P<sent>\d+)'),
  'status': re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*STATUS node=(?P<node>\d+) energy_mj=(?P<e>\d+) duty_pct=(?P<duty>-?\d+) rank=(?P<rank>\d+)'),
  'rx':     re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*RX sink=(?P<sink>\d+) cluster=(?P<cl>\d+) node=(?P<node>\d+) seq=(?P<seq>\d+) energy_mj=(?P<e>\d+) bytes=(?P<b>\d+) latency_ms=(?P<lat>\d+)'),
  'health': re.compile(r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*HEALTH sink=(?P<sink>\d+) active_routes=(?P<n>\d+)'),
}

def parse(path):
  out = {k: [] for k in PATTERNS}
  with open(path) as f:
    for line in f:
      for key, pat in PATTERNS.items():
        m = pat.search(line)
        if m:
          out[key].append(m.groupdict())
          break
  return {k: pd.DataFrame(v) for k, v in out.items()}

def to_num(df, cols):
  for c in cols:
    if c in df.columns:
      df[c] = pd.to_numeric(df[c])
  return df

def cooja_time_to_s(series):
  # Cooja time format: số milliseconds
  # Chuyển sang giây
  return pd.to_numeric(series, errors='coerce') / 1000.0

def normalize_time(tx, rx, dead, status, gen):
  """Normalize timestamps so they start from 0"""
  # Tìm timestamp nhỏ nhất trong tất cả các dataframes
  min_time = float('inf')
  for df in [tx, rx, dead, status, gen]:
    if len(df) > 0 and 't_s' in df.columns:
      min_time = min(min_time, df['t_s'].min())
  
  # Trừ đi min_time để chuẩn hóa về 0
  if min_time < float('inf') and min_time > 0:
    for df in [tx, rx, dead, status, gen]:
      if len(df) > 0 and 't_s' in df.columns:
        df['t_s'] = df['t_s'] - min_time
  
  return tx, rx, dead, status, gen

def create_visualizations(full_df, metrics_df, rx, tx, dead, status, gen, output_dir):
  """Tạo 3 charts QUAN TRỌNG NHẤT - Clean & Clear"""
  
  # Loại bỏ hàng TRUNG_BINH để vẽ chart
  plot_df = metrics_df[metrics_df['node'] != 'TRUNG_BINH'].copy()
  plot_df['node'] = plot_df['node'].astype(int)
  plot_df = plot_df.sort_values('node')
  
  # Tạo thư mục charts
  charts_dir = output_dir / 'charts'
  charts_dir.mkdir(exist_ok=True)
  
  # ========== CHART 1: NETWORK PERFORMANCE OVERVIEW (KEY METRICS) ==========
  fig = plt.figure(figsize=(16, 10))
  fig.suptitle('NETWORK PERFORMANCE OVERVIEW', fontsize=18, fontweight='bold', y=0.98)
  
  gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)
  
  # 1.1 PDR (Packet Delivery Ratio)
  ax1 = fig.add_subplot(gs[0, 0])
  total_tx = full_df['packets_sent'].sum()
  total_rx = full_df['packets_received'].sum()
  pdr = (total_rx / total_tx * 100) if total_tx > 0 else 0
  
  colors = ['#2ecc71' if pdr > 90 else '#e74c3c' if pdr < 70 else '#f39c12']
  ax1.bar(['PDR'], [pdr], color=colors[0], edgecolor='black', linewidth=2, width=0.5)
  ax1.axhline(y=90, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Good (>90%)')
  ax1.axhline(y=70, color='red', linestyle='--', linewidth=2, alpha=0.5, label='Bad (<70%)')
  ax1.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
  ax1.set_title('Packet Delivery Ratio', fontsize=13, fontweight='bold')
  ax1.set_ylim(0, 110)
  ax1.text(0, pdr + 3, f'{pdr:.1f}%', ha='center', fontsize=16, fontweight='bold')
  ax1.legend(fontsize=8, loc='upper right')
  ax1.grid(axis='y', alpha=0.3)
  
  # 1.2 Average Throughput
  ax2 = fig.add_subplot(gs[0, 1])
  avg_thr = plot_df['thong_luong_sensor_to_sink_bps'].mean()
  ax2.bar(['Throughput'], [avg_thr], color='#3498db', edgecolor='black', linewidth=2, width=0.5)
  ax2.set_ylabel('bps', fontsize=12, fontweight='bold')
  ax2.set_title('Average Throughput (Sensor → Sink)', fontsize=13, fontweight='bold')
  ax2.text(0, avg_thr * 1.05, f'{avg_thr:.4f}', ha='center', fontsize=14, fontweight='bold')
  ax2.grid(axis='y', alpha=0.3)
  
  # 1.3 Average Latency
  ax3 = fig.add_subplot(gs[0, 2])
  avg_lat = rx['lat'].mean() if len(rx) > 0 else 0
  color_lat = '#2ecc71' if avg_lat < 500 else '#e74c3c' if avg_lat > 1000 else '#f39c12'
  ax3.bar(['Latency'], [avg_lat], color=color_lat, edgecolor='black', linewidth=2, width=0.5)
  ax3.axhline(y=500, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Good (<500ms)')
  ax3.axhline(y=1000, color='red', linestyle='--', linewidth=2, alpha=0.5, label='Bad (>1000ms)')
  ax3.set_ylabel('Milliseconds (ms)', fontsize=12, fontweight='bold')
  ax3.set_title('Average End-to-End Latency', fontsize=13, fontweight='bold')
  ax3.text(0, avg_lat * 1.05, f'{avg_lat:.1f}', ha='center', fontsize=14, fontweight='bold')
  ax3.legend(fontsize=8, loc='upper right')
  ax3.grid(axis='y', alpha=0.3)
  
  # 1.4 Energy Efficiency by Cluster
  ax4 = fig.add_subplot(gs[1, :])
  cluster_stats = plot_df.groupby('cluster').agg({
    'hieu_qua_nang_luong_bytes_per_joule': 'mean',
    'node': 'count'
  }).reset_index()
  cluster_stats.columns = ['cluster', 'avg_energy_eff', 'node_count']
  
  bars = ax4.bar(cluster_stats['cluster'].astype(str), cluster_stats['avg_energy_eff'], 
                 color=['#9b59b6', '#e67e22'], edgecolor='black', linewidth=1.5, alpha=0.8)
  ax4.set_xlabel('Cluster ID', fontsize=12, fontweight='bold')
  ax4.set_ylabel('Bytes/Joule', fontsize=12, fontweight='bold')
  ax4.set_title('Energy Efficiency by Cluster (Average)', fontsize=13, fontweight='bold')
  ax4.grid(axis='y', alpha=0.3)
  
  for i, (bar, count, eff) in enumerate(zip(bars, cluster_stats['node_count'], cluster_stats['avg_energy_eff'])):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height * 1.02,
             f'{eff:.1f}\n({count} nodes)', ha='center', fontsize=11, fontweight='bold')
  
  # 1.5 Top 10 & Bottom 10 Nodes by Energy Efficiency
  ax5 = fig.add_subplot(gs[2, :])
  
  # Sort và lấy top/bottom
  sorted_df = plot_df.sort_values('hieu_qua_nang_luong_bytes_per_joule', ascending=False)
  top10 = sorted_df.head(10)
  bottom10 = sorted_df.tail(10)
  
  combined = pd.concat([top10, bottom10])
  colors_combined = ['#2ecc71'] * 10 + ['#e74c3c'] * 10
  
  bars = ax5.barh(combined['node'].astype(str), combined['hieu_qua_nang_luong_bytes_per_joule'],
                  color=colors_combined, edgecolor='black', linewidth=0.8, alpha=0.8)
  ax5.set_xlabel('Energy Efficiency (Bytes/Joule)', fontsize=12, fontweight='bold')
  ax5.set_ylabel('Node ID', fontsize=12, fontweight='bold')
  ax5.set_title('Energy Efficiency: Top 10 (Green) vs Bottom 10 (Red)', fontsize=13, fontweight='bold')
  ax5.axvline(x=0, color='black', linewidth=1)
  ax5.grid(axis='x', alpha=0.3)
  
  # Thêm annotation
  ax5.text(0.02, 0.95, 'Top 10 →', transform=ax5.transAxes, fontsize=11, 
           fontweight='bold', color='#2ecc71', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
  ax5.text(0.02, 0.05, '← Bottom 10', transform=ax5.transAxes, fontsize=11,
           fontweight='bold', color='#e74c3c', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
  
  plt.savefig(charts_dir / '1_network_overview.png', dpi=300, bbox_inches='tight')
  plt.close()
  print(f"  ✅ Chart 1: Network Performance Overview")
  
  # ========== CHART 2: ENERGY & LIFETIME ANALYSIS ==========
  fig, axes = plt.subplots(2, 2, figsize=(16, 10))
  fig.suptitle('ENERGY & LIFETIME ANALYSIS', fontsize=18, fontweight='bold')
  
  # 2.1 Energy Consumption Over Time (Aggregated by Cluster)
  ax1 = axes[0, 0]
  if len(status) > 0:
    for cluster in sorted(plot_df['cluster'].unique()):
      cluster_nodes = plot_df[plot_df['cluster'] == cluster]['node'].values
      cluster_energy = []
      cluster_time = []
      
      for node in cluster_nodes:
        node_status = status[status['node'] == node].sort_values('t_s')
        if len(node_status) > 0:
          for _, row in node_status.iterrows():
            cluster_energy.append(row['e'])
            cluster_time.append(row['t_s'])
      
      if cluster_time:
        # Aggregate by time bins
        time_bins = np.linspace(min(cluster_time), max(cluster_time), 50)
        energy_bins = []
        time_centers = []
        
        for i in range(len(time_bins) - 1):
          mask = (np.array(cluster_time) >= time_bins[i]) & (np.array(cluster_time) < time_bins[i+1])
          if mask.any():
            energy_bins.append(np.mean(np.array(cluster_energy)[mask]))
            time_centers.append((time_bins[i] + time_bins[i+1]) / 2)
        
        ax1.plot(time_centers, energy_bins, marker='o', linewidth=2.5, 
                markersize=5, label=f'Cluster {cluster}', alpha=0.8)
  
  ax1.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
  ax1.set_ylabel('Remaining Energy (mJ)', fontsize=12, fontweight='bold')
  ax1.set_title('Energy Depletion Over Time (by Cluster)', fontsize=13, fontweight='bold')
  ax1.legend(fontsize=11)
  ax1.grid(True, alpha=0.3)
  
  # 2.2 Node Lifetime Distribution
  ax2 = axes[0, 1]
  if len(dead) > 0:
    dead_with_cluster = dead.merge(plot_df[['node', 'cluster']], on='node', how='left')
    
    for cluster in sorted(dead_with_cluster['cluster'].dropna().unique()):
      cluster_dead = dead_with_cluster[dead_with_cluster['cluster'] == cluster]['alive']
      ax2.hist(cluster_dead, bins=10, alpha=0.6, label=f'Cluster {int(cluster)}', edgecolor='black')
    
    ax2.set_xlabel('Lifetime (seconds)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Number of Nodes', fontsize=12, fontweight='bold')
    ax2.set_title('Node Lifetime Distribution', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=11)
    ax2.grid(axis='y', alpha=0.3)
  else:
    ax2.text(0.5, 0.5, 'No nodes died during simulation', 
             ha='center', va='center', fontsize=12, transform=ax2.transAxes)
    ax2.set_title('Node Lifetime Distribution', fontsize=13, fontweight='bold')
  
  # 2.3 FND, HND, LND Analysis
  ax3 = axes[1, 0]
  if len(dead) > 0:
    sorted_dead = dead.sort_values('alive')
    fnd = sorted_dead['alive'].iloc[0] if len(sorted_dead) > 0 else 0
    hnd = sorted_dead['alive'].iloc[len(sorted_dead)//2] if len(sorted_dead) > 1 else 0
    lnd = sorted_dead['alive'].iloc[-1] if len(sorted_dead) > 0 else 0
    
    metrics = ['FND\n(First)', 'HND\n(Half)', 'LND\n(Last)']
    values = [fnd, hnd, lnd]
    colors_fnd = ['#e74c3c', '#f39c12', '#2ecc71']
    
    bars = ax3.bar(metrics, values, color=colors_fnd, edgecolor='black', linewidth=2, width=0.6)
    ax3.set_ylabel('Time (seconds)', fontsize=12, fontweight='bold')
    ax3.set_title('Network Lifetime: FND / HND / LND', fontsize=13, fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    
    for bar, val in zip(bars, values):
      height = bar.get_height()
      ax3.text(bar.get_x() + bar.get_width()/2., height * 1.02,
               f'{int(val)}s', ha='center', fontsize=12, fontweight='bold')
  else:
    ax3.text(0.5, 0.5, 'No node deaths recorded', 
             ha='center', va='center', fontsize=12, transform=ax3.transAxes)
    ax3.set_title('Network Lifetime: FND / HND / LND', fontsize=13, fontweight='bold')
  
  # 2.4 Data Transmitted Before Death (Top 10)
  ax4 = axes[1, 1]
  top10_data = plot_df.nlargest(10, 'data_truyen_duoc_truoc_khi_het_pin_bytes')
  
  bars = ax4.barh(top10_data['node'].astype(str), top10_data['data_truyen_duoc_truoc_khi_het_pin_bytes'],
                  color='#3498db', edgecolor='black', linewidth=1, alpha=0.8)
  ax4.set_xlabel('Bytes', fontsize=12, fontweight='bold')
  ax4.set_ylabel('Node ID', fontsize=12, fontweight='bold')
  ax4.set_title('Top 10: Data Transmitted Before Energy Depletion', fontsize=13, fontweight='bold')
  ax4.grid(axis='x', alpha=0.3)
  
  for bar in bars:
    width = bar.get_width()
    ax4.text(width * 1.02, bar.get_y() + bar.get_height()/2.,
             f'{int(width)}', va='center', fontsize=10, fontweight='bold')
  
  plt.tight_layout()
  plt.savefig(charts_dir / '2_energy_lifetime.png', dpi=300, bbox_inches='tight')
  plt.close()
  print(f"  ✅ Chart 2: Energy & Lifetime Analysis")
  
  # ========== CHART 3: NETWORK HEALTH INDICATORS ==========
  fig, axes = plt.subplots(2, 2, figsize=(16, 10))
  fig.suptitle('NETWORK HEALTH INDICATORS', fontsize=18, fontweight='bold')
  
  # 3.1 Throughput vs Data Generation Rate (Cluster Average)
  ax1 = axes[0, 0]
  cluster_rate = plot_df.groupby('cluster').agg({
    'thong_luong_sensor_to_sink_bps': 'mean',
    'toc_do_tao_gui_du_lieu_bps': 'mean'
  }).reset_index()
  
  x = np.arange(len(cluster_rate))
  width = 0.35
  
  bars1 = ax1.bar(x - width/2, cluster_rate['toc_do_tao_gui_du_lieu_bps'], width,
                  label='Data Generation Rate', color='#f39c12', edgecolor='black', linewidth=1.5)
  bars2 = ax1.bar(x + width/2, cluster_rate['thong_luong_sensor_to_sink_bps'], width,
                  label='Throughput (RX at Sink)', color='#16a085', edgecolor='black', linewidth=1.5)
  
  ax1.set_xlabel('Cluster ID', fontsize=12, fontweight='bold')
  ax1.set_ylabel('Rate (bps)', fontsize=12, fontweight='bold')
  ax1.set_title('Data Rate vs Throughput (Cluster Average)', fontsize=13, fontweight='bold')
  ax1.set_xticks(x)
  ax1.set_xticklabels(cluster_rate['cluster'].astype(int))
  ax1.legend(fontsize=11)
  ax1.grid(axis='y', alpha=0.3)
  
  # 3.2 Latency Box Plot (by Cluster)
  ax2 = axes[0, 1]
  if len(rx) > 0:
    rx_with_cluster = rx.merge(plot_df[['node', 'cluster']], on='node', how='left')
    latency_by_cluster = [rx_with_cluster[rx_with_cluster['cluster'] == c]['lat'].values 
                          for c in sorted(rx_with_cluster['cluster'].dropna().unique())]
    labels_cluster = [f'C{int(c)}' for c in sorted(rx_with_cluster['cluster'].dropna().unique())]
    
    bp = ax2.boxplot(latency_by_cluster, labels=labels_cluster, patch_artist=True,
                     boxprops=dict(facecolor='#3498db', color='black', linewidth=1.5),
                     medianprops=dict(color='red', linewidth=2.5),
                     whiskerprops=dict(color='black', linewidth=1.5),
                     capprops=dict(color='black', linewidth=1.5))
    
    ax2.axhline(y=500, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Target: 500ms')
    ax2.set_xlabel('Cluster ID', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Latency (ms)', fontsize=12, fontweight='bold')
    ax2.set_title('Latency Distribution by Cluster', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3)
  
  # 3.3 Packet Loss Analysis (by Cluster)
  ax3 = axes[1, 0]
  cluster_packets = plot_df.groupby('cluster').agg({
    'node': 'count'
  }).reset_index()
  cluster_packets.columns = ['cluster', 'node_count']
  
  cluster_tx = full_df.groupby(plot_df['cluster'])['packets_sent'].sum().reset_index()
  cluster_rx = full_df.groupby(plot_df['cluster'])['packets_received'].sum().reset_index()
  cluster_tx.columns = ['cluster', 'tx']
  cluster_rx.columns = ['cluster', 'rx']
  
  cluster_pdr = cluster_tx.merge(cluster_rx, on='cluster')
  cluster_pdr['pdr'] = (cluster_pdr['rx'] / cluster_pdr['tx'] * 100).fillna(0)
  cluster_pdr['loss'] = 100 - cluster_pdr['pdr']
  
  x = np.arange(len(cluster_pdr))
  width = 0.35
  
  bars1 = ax3.bar(x - width/2, cluster_pdr['pdr'], width, 
                  label='Delivered (%)', color='#2ecc71', edgecolor='black', linewidth=1.5)
  bars2 = ax3.bar(x + width/2, cluster_pdr['loss'], width,
                  label='Lost (%)', color='#e74c3c', edgecolor='black', linewidth=1.5)
  
  ax3.axhline(y=90, color='green', linestyle='--', linewidth=2, alpha=0.5)
  ax3.set_xlabel('Cluster ID', fontsize=12, fontweight='bold')
  ax3.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
  ax3.set_title('Packet Delivery & Loss by Cluster', fontsize=13, fontweight='bold')
  ax3.set_xticks(x)
  ax3.set_xticklabels(cluster_pdr['cluster'].astype(int))
  ax3.legend(fontsize=11)
  ax3.set_ylim(0, 110)
  ax3.grid(axis='y', alpha=0.3)
  
  for i, (bar1, bar2, pdr, loss) in enumerate(zip(bars1, bars2, cluster_pdr['pdr'], cluster_pdr['loss'])):
    ax3.text(bar1.get_x() + bar1.get_width()/2., pdr + 2,
             f'{pdr:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax3.text(bar2.get_x() + bar2.get_width()/2., loss + 2,
             f'{loss:.1f}%', ha='center', fontsize=10, fontweight='bold')
  
  # 3.4 Summary Statistics Table
  ax4 = axes[1, 1]
  ax4.axis('off')
  
  summary_stats = [
    ['Metric', 'Value'],
    ['─' * 30, '─' * 20],
    ['Total Nodes', f'{len(plot_df)}'],
    ['Active Clusters', f'{plot_df["cluster"].nunique()}'],
    ['Total Packets Sent', f'{int(total_tx)}'],
    ['Total Packets Received', f'{int(total_rx)}'],
    ['Overall PDR', f'{pdr:.2f}%'],
    ['Avg Throughput', f'{avg_thr:.4f} bps'],
    ['Avg Latency', f'{avg_lat:.1f} ms'],
    ['Nodes Died', f'{len(dead)}'],
    ['Simulation Time', f'{rx["t_s"].max():.0f}s' if len(rx) > 0 else 'N/A'],
  ]
  
  table = ax4.table(cellText=summary_stats, cellLoc='left', loc='center',
                    colWidths=[0.6, 0.4], bbox=[0.1, 0.1, 0.8, 0.8])
  table.auto_set_font_size(False)
  table.set_fontsize(11)
  table.scale(1, 2)
  
  # Style header
  for i in range(2):
    table[(0, i)].set_facecolor('#34495e')
    table[(0, i)].set_text_props(weight='bold', color='white', fontsize=12)
  
  # Style rows
  for i in range(2, len(summary_stats)):
    for j in range(2):
      table[(i, j)].set_facecolor('#ecf0f1' if i % 2 == 0 else 'white')
      if j == 1:
        table[(i, j)].set_text_props(weight='bold')
  
  ax4.set_title('Network Summary Statistics', fontsize=13, fontweight='bold', pad=20)
  
  plt.tight_layout()
  plt.savefig(charts_dir / '3_network_health.png', dpi=300, bbox_inches='tight')
  plt.close()
  print(f"  ✅ Chart 3: Network Health Indicators")
  
  print(f"\n  🎯 Tổng cộng: 3 charts QUAN TRỌNG đã được tạo trong {charts_dir}")

def analyze(path, payload_bytes=16):
  d = parse(path)
  tx = to_num(d['tx'].copy(), ['cl','node','seq','e','b'])
  rx = to_num(d['rx'].copy(), ['sink','cl','node','seq','e','b','lat'])
  dead = to_num(d['dead'].copy(), ['cl','node','alive','seq','gen','sent'])
  
  # ✅ FIX: Chỉ lấy DEAD event ĐẦU TIÊN của mỗi node (loại bỏ duplicates)
  if len(dead) > 0:
    dead = dead.sort_values('alive').groupby('node').first().reset_index()
    print(f"\n🔧 Fixed: Removed duplicate DEAD events. Unique dead nodes: {len(dead)}")
  
  status = to_num(d['status'].copy(), ['node','e','duty','rank'])
  gen = to_num(d['gen'].copy(), ['cl','node','gc'])

  for df in (tx, rx, dead, status, gen):
    if 't' in df.columns and len(df):
      df['t_s'] = cooja_time_to_s(df['t'])

  # Tìm timestamp nhỏ nhất TOÀN CỤC từ tất cả các events
  min_time = float('inf')
  for df in [tx, rx, dead, status, gen]:
    if len(df) > 0 and 't_s' in df.columns and df['t_s'].notna().any():
      df_min = df['t_s'].min()
      if df_min < min_time:
        min_time = df_min
  
  print(f"\n🕐 Debug: Global min_time = {min_time:.2f}s")
  
  # Trừ đi min_time để chuẩn hóa về 0
  if min_time < float('inf') and min_time > 0:
    tx['t_s'] = tx['t_s'] - min_time
    rx['t_s'] = rx['t_s'] - min_time
    dead['t_s'] = dead['t_s'] - min_time
    status['t_s'] = status['t_s'] - min_time
    gen['t_s'] = gen['t_s'] - min_time
  
  print(f"   After normalize: tx.t_s range = [{tx['t_s'].min():.2f}, {tx['t_s'].max():.2f}]s" if len(tx) else "   No TX data")
  print(f"   After normalize: rx.t_s range = [{rx['t_s'].min():.2f}, {rx['t_s'].max():.2f}]s" if len(rx) else "   No RX data")
  print(f"   After normalize: gen.t_s range = [{gen['t_s'].min():.2f}, {gen['t_s'].max():.2f}]s" if len(gen) else "   No GEN data")

  # ========== BẮT ĐẦU TÍNH TOÁN ==========
  
  print("\n===== Total RX Bytes & Packets Received tại Sink (per node) =====")
  rxg = rx.groupby('node').agg(packets_received=('seq','count'), rx_bytes=('b','sum'))
  print(rxg)

  txg = tx.groupby('node').agg(packets_sent=('seq','count'), tx_bytes=('b','sum'))
  
  total_time_s = rx['t_s'].max() if len(rx) and rx['t_s'].max() > 0 else 1
  gen_time_s = gen['t_s'].max() if len(gen) and gen['t_s'].max() > 0 else 1

  print(f"\n⏱️  Thời gian simulation: {total_time_s:.2f}s ({total_time_s/60:.2f} phút)")

  
  thr = (rxg['rx_bytes'] * 8) / total_time_s if total_time_s > 0 else pd.Series(dtype=float)
  gen_rate_per_node = (gen.groupby('node')['gc'].max() * payload_bytes * 8) / gen_time_s if gen_time_s > 0 else pd.Series(dtype=float)
  
  rank_avg = status.groupby('node')['rank'].mean() if len(status) else pd.Series(dtype=float)
  duty_avg = status.groupby('node')['duty'].mean() if len(status) else pd.Series(dtype=float)
  
  def count_switches(s):
    diffs = s.diff().abs()
    return (diffs > diffs.mean() + 2 * diffs.std()).sum() if len(s) > 2 else 0
  parent_switches = status.groupby('node')['rank'].apply(count_switches) if len(status) else pd.Series(dtype=float)

  # Energy calculation
  INITIAL_ENERGY_MJ = 7200  # ✅ FIX: Phải khớp với node.c
  last_energy = status.groupby('node')['e'].min() if len(status) else pd.Series(dtype=float)
  energy_used_j = (INITIAL_ENERGY_MJ - last_energy) / 1000.0
  
  # ✅ FIX: Xử lý energy âm (bug trong STATUS log)
  energy_used_j = energy_used_j.clip(lower=0.001)  # Không cho phép energy = 0 hoặc âm
  
  data_per_joule = (rxg['rx_bytes'] / energy_used_j).replace([np.inf, -np.inf], np.nan)

  # ========== TẠO FILE CSV ==========
  
  output_dir = Path(path).parent.parent / 'results'
  output_dir.mkdir(exist_ok=True)
  
  # Chuẩn bị dữ liệu với index chung
  all_nodes = sorted(rxg.index.tolist())
  
  # FILE 2: 4 CHỈ SỐ CHÍNH - Chi tiết theo node
  metrics_data = []
  for node in all_nodes:
    row = {
      'node': node,
      'cluster': int(rx[rx['node'] == node]['cl'].iloc[0]) if node in rx['node'].values else 0,
      'data_truyen_duoc_truoc_khi_het_pin_bytes': rxg.loc[node, 'rx_bytes'] if node in rxg.index else 0,
      'thoi_gian_song_s': dead[dead['node'] == node]['alive'].iloc[0] if node in dead['node'].values else np.nan,
      'thong_luong_sensor_to_sink_bps': thr.loc[node] if node in thr.index else 0,
      'toc_do_tao_gui_du_lieu_bps': gen_rate_per_node.loc[node] if node in gen_rate_per_node.index else 0,
      'hieu_qua_nang_luong_bytes_per_joule': data_per_joule.loc[node] if node in data_per_joule.index else 0
    }
    metrics_data.append(row)
  
  metrics_df = pd.DataFrame(metrics_data)
  
  # Thêm hàng tổng kết
  summary_row = pd.DataFrame([{
    'node': 'TRUNG_BINH',
    'cluster': '',
    'data_truyen_duoc_truoc_khi_het_pin_bytes': metrics_df['data_truyen_duoc_truoc_khi_het_pin_bytes'].mean(),
    'thoi_gian_song_s': metrics_df['thoi_gian_song_s'].mean(),
    'thong_luong_sensor_to_sink_bps': metrics_df['thong_luong_sensor_to_sink_bps'].mean(),
    'toc_do_tao_gui_du_lieu_bps': metrics_df['toc_do_tao_gui_du_lieu_bps'].mean(),
    'hieu_qua_nang_luong_bytes_per_joule': metrics_df['hieu_qua_nang_luong_bytes_per_joule'].mean()
  }])
  
  metrics_final = pd.concat([metrics_df, summary_row], ignore_index=True)
  
  summary_csv = output_dir / 'summary_4metrics.csv'
  metrics_final.to_csv(summary_csv, index=False, encoding='utf-8-sig')
  print(f"\n✅ Đã lưu 4 chỉ số chính: {summary_csv}")
  
  # FILE 1: FULL ANALYSIS
  full_data = []
  for node in all_nodes:
    row = {
      'node': node,
      'cluster': int(rx[rx['node'] == node]['cl'].iloc[0]) if node in rx['node'].values else 0,
      'packets_sent': txg.loc[node, 'packets_sent'] if node in txg.index else 0,
      'tx_bytes': txg.loc[node, 'tx_bytes'] if node in txg.index else 0,
      'packets_received': rxg.loc[node, 'packets_received'],
      'rx_bytes': rxg.loc[node, 'rx_bytes'],
      'throughput_bps': thr.loc[node] if node in thr.index else 0,
      'gen_rate_bps': gen_rate_per_node.loc[node] if node in gen_rate_per_node.index else 0,
      'avg_latency_ms': rx[rx['node'] == node]['lat'].mean() if node in rx['node'].values else 0,
      'p95_latency_ms': rx[rx['node'] == node]['lat'].quantile(0.95) if node in rx['node'].values else 0,
      'avg_rank': rank_avg.loc[node] if node in rank_avg.index else 0,
      'parent_switches': parent_switches.loc[node] if node in parent_switches.index else 0,
      'avg_duty_cycle_pct': duty_avg.loc[node] if node in duty_avg.index else 0,
      'time_alive_s': dead[dead['node'] == node]['alive'].iloc[0] if node in dead['node'].values else np.nan,
      'energy_used_j': energy_used_j.loc[node] if node in energy_used_j.index else 0,
      'data_per_joule': data_per_joule.loc[node] if node in data_per_joule.index else 0
    }
    full_data.append(row)
  
  full_df = pd.DataFrame(full_data)
  full_csv = output_dir / 'full_analysis.csv'
  full_df.to_csv(full_csv, index=False, encoding='utf-8-sig')
  print(f"✅ Đã lưu phân tích đầy đủ: {full_csv}")
  
  print(f"\n📊 Tổng kết:")
  print(f"  - Tổng số nodes: {len(all_nodes)}")
  print(f"  - Nodes đã chết (unique): {len(dead)}")
  print(f"  - Tổng packets sent: {txg['packets_sent'].sum() if len(txg) else 0}")
  print(f"  - Tổng packets nhận: {rxg['packets_received'].sum()}")
  print(f"  - PDR: {(rxg['packets_received'].sum() / txg['packets_sent'].sum() * 100) if len(txg) and txg['packets_sent'].sum() > 0 else 0:.2f}%")
  print(f"  - Tổng bytes nhận: {rxg['rx_bytes'].sum()}")
  print(f"  - Thời gian mô phỏng: {total_time_s:.2f}s ({total_time_s/3600:.2f} giờ)")
  print(f"  - Network throughput: {(rxg['rx_bytes'].sum() * 8 / total_time_s):.6f} bps")
  
  # ========== TẠO VISUALIZATION ==========
  print("\n🎨 Đang tạo 3 charts QUAN TRỌNG (Clean & Professional)...")
  create_visualizations(full_df, metrics_final, rx, tx, dead, status, gen, output_dir)
  print(f"\n✅ Hoàn thành! Tất cả kết quả đã lưu vào: {output_dir}")

if __name__ == '__main__':
  import os
  
  if len(sys.argv) > 1:
    log_path = sys.argv[1]
  else:
    # Tự động tìm file log mới nhất trong data/logs/
    log_dir = Path(__file__).parent / 'data' / 'logs'
    if not log_dir.exists():
      print(f"Error: Thư mục {log_dir} không tồn tại!")
      print("Vui lòng chạy simulation trước hoặc chỉ định đường dẫn log:")
      print(f"  python {sys.argv[0]} <path_to_log_file>")
      sys.exit(1)
    
    log_files = list(log_dir.glob('*.log'))
    if not log_files:
      print(f"Error: Không tìm thấy file .log trong {log_dir}")
      print("Vui lòng chạy simulation trước!")
      sys.exit(1)
    
    # Lấy file log mới nhất
    log_path = max(log_files, key=lambda p: p.stat().st_mtime)
    print(f"Đang phân tích file log: {log_path}\n")
  
  analyze(log_path)
