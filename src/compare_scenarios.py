import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from analyze import parse, to_num, cooja_time_to_s

sns.set_style("whitegrid")
sns.set_palette("husl")

def load_scenario(log_path, label):
    """Load and process one scenario"""
    d = parse(log_path)
    tx = to_num(d['tx'].copy(), ['cl','node','seq','e','b'])
    rx = to_num(d['rx'].copy(), ['sink','cl','node','seq','e','b','lat'])
    dead = to_num(d['dead'].copy(), ['cl','node','alive','seq','gen','sent'])
    status = to_num(d['status'].copy(), ['node','e','duty','rank'])
    gen = to_num(d['gen'].copy(), ['cl','node','gc'])
    
    for df in (tx, rx, dead, status, gen):
        if 't' in df.columns and len(df):
            df['t_s'] = cooja_time_to_s(df['t'])
    
    # Normalize time
    min_time = float('inf')
    for df in [tx, rx, dead, status, gen]:
        if len(df) > 0 and 't_s' in df.columns and df['t_s'].notna().any():
            df_min = df['t_s'].min()
            if df_min < min_time:
                min_time = df_min
    
    if min_time < float('inf') and min_time > 0:
        tx['t_s'] = tx['t_s'] - min_time
        rx['t_s'] = rx['t_s'] - min_time
        dead['t_s'] = dead['t_s'] - min_time
        status['t_s'] = status['t_s'] - min_time
        gen['t_s'] = gen['t_s'] - min_time
    
    # Calculate metrics
    rxg = rx.groupby('node').agg(packets_received=('seq','count'), rx_bytes=('b','sum'))
    txg = tx.groupby('node').agg(packets_sent=('seq','count'), tx_bytes=('b','sum'))
    
    total_time_s = rx['t_s'].max() if len(rx) and rx['t_s'].max() > 0 else 1
    
    thr = (rxg['rx_bytes'] * 8) / total_time_s if total_time_s > 0 else pd.Series(dtype=float)
    duty_avg = status.groupby('node')['duty'].mean() if len(status) else pd.Series(dtype=float)
    
    INITIAL_ENERGY_MJ = 7200
    last_energy = status.groupby('node')['e'].min() if len(status) else pd.Series(dtype=float)
    energy_used_j = (INITIAL_ENERGY_MJ - last_energy) / 1000.0
    
    summary = {
        'label': label,
        'total_packets_sent': txg['packets_sent'].sum() if len(txg) else 0,
        'total_packets_received': rxg['packets_received'].sum() if len(rxg) else 0,
        'pdr': (rxg['packets_received'].sum() / txg['packets_sent'].sum() * 100) if len(txg) and txg['packets_sent'].sum() > 0 else 0,
        'avg_throughput': thr.mean() if len(thr) else 0,
        'avg_latency': rx['lat'].mean() if len(rx) else 0,
        'avg_duty_cycle': duty_avg.mean() if len(duty_avg) else 0,
        'avg_energy_used': energy_used_j.mean() if len(energy_used_j) else 0,
        'nodes_died': len(dead),
        'fnd': dead['alive'].min() if len(dead) else None,  # First Node Death
        'lnd': dead['alive'].max() if len(dead) else None,  # Last Node Death
    }
    
    return {
        'summary': summary,
        'rx': rx,
        'tx': tx,
        'dead': dead,
        'status': status,
        'rxg': rxg,
        'txg': txg,
        'thr': thr,
        'duty_avg': duty_avg,
        'energy_used_j': energy_used_j
    }

def compare_scenarios(scenario1, scenario2, output_dir):
    """Create comparison charts"""
    
    charts_dir = output_dir / 'comparison_charts'
    charts_dir.mkdir(exist_ok=True)
    
    s1 = scenario1['summary']
    s2 = scenario2['summary']
    
    # ========== 1. SUMMARY COMPARISON ==========
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f'Scenario Comparison: {s1["label"]} vs {s2["label"]}', 
                 fontsize=16, fontweight='bold')
    
    metrics = [
        ('pdr', 'Packet Delivery Ratio (%)', 'steelblue'),
        ('avg_throughput', 'Avg Throughput (bps)', 'coral'),
        ('avg_latency', 'Avg Latency (ms)', 'mediumseagreen'),
        ('avg_duty_cycle', 'Avg Duty Cycle (%)', 'orange'),
        ('avg_energy_used', 'Avg Energy Used (J)', 'mediumpurple'),
        ('nodes_died', 'Nodes Died', 'crimson')
    ]
    
    for idx, (metric, title, color) in enumerate(metrics):
        ax = axes[idx // 3, idx % 3]
        values = [s1[metric], s2[metric]]
        labels = [s1['label'], s2['label']]
        
        bars = ax.bar(labels, values, color=color, edgecolor='black', linewidth=1.5, alpha=0.8)
        ax.set_title(title, fontweight='bold', fontsize=11)
        ax.grid(axis='y', alpha=0.3)
        
        # Add values on bars
        for bar in bars:
            height = bar.get_height()
            if height is not None and not pd.isna(height):
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.2f}', ha='center', va='bottom', fontweight='bold')
        
        # Highlight better value
        if metric in ['pdr', 'avg_throughput'] and values[0] > values[1]:
            bars[0].set_edgecolor('green')
            bars[0].set_linewidth(3)
        elif metric in ['pdr', 'avg_throughput'] and values[1] > values[0]:
            bars[1].set_edgecolor('green')
            bars[1].set_linewidth(3)
        elif metric in ['avg_latency', 'avg_duty_cycle', 'avg_energy_used', 'nodes_died'] and values[0] < values[1]:
            bars[0].set_edgecolor('green')
            bars[0].set_linewidth(3)
        elif metric in ['avg_latency', 'avg_duty_cycle', 'avg_energy_used', 'nodes_died'] and values[1] < values[0]:
            bars[1].set_edgecolor('green')
            bars[1].set_linewidth(3)
    
    plt.tight_layout()
    plt.savefig(charts_dir / '1_summary_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # ========== 2. THROUGHPUT COMPARISON (per node) ==========
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Merge throughput data
    thr1 = scenario1['thr'].reset_index()
    thr1.columns = ['node', s1['label']]
    thr2 = scenario2['thr'].reset_index()
    thr2.columns = ['node', s2['label']]
    
    thr_merged = pd.merge(thr1, thr2, on='node', how='outer').fillna(0)
    thr_merged = thr_merged.sort_values('node')
    
    x = range(len(thr_merged))
    width = 0.35
    
    ax.bar([i - width/2 for i in x], thr_merged[s1['label']], width, 
           label=s1['label'], color='steelblue', edgecolor='black', linewidth=0.5)
    ax.bar([i + width/2 for i in x], thr_merged[s2['label']], width,
           label=s2['label'], color='coral', edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Node ID', fontsize=12)
    ax.set_ylabel('Throughput (bps)', fontsize=12)
    ax.set_title('Throughput Comparison per Node', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(thr_merged['node'].astype(int))
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(charts_dir / '2_throughput_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # ========== 3. ENERGY CONSUMPTION COMPARISON ==========
    fig, ax = plt.subplots(figsize=(14, 7))
    
    energy1 = scenario1['energy_used_j'].reset_index()
    energy1.columns = ['node', s1['label']]
    energy2 = scenario2['energy_used_j'].reset_index()
    energy2.columns = ['node', s2['label']]
    
    energy_merged = pd.merge(energy1, energy2, on='node', how='outer').fillna(0)
    energy_merged = energy_merged.sort_values('node')
    
    x = range(len(energy_merged))
    width = 0.35
    
    ax.bar([i - width/2 for i in x], energy_merged[s1['label']], width,
           label=s1['label'], color='mediumseagreen', edgecolor='black', linewidth=0.5)
    ax.bar([i + width/2 for i in x], energy_merged[s2['label']], width,
           label=s2['label'], color='crimson', edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Node ID', fontsize=12)
    ax.set_ylabel('Energy Used (Joules)', fontsize=12)
    ax.set_title('Energy Consumption Comparison per Node', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(energy_merged['node'].astype(int))
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(charts_dir / '3_energy_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # ========== 4. DUTY CYCLE COMPARISON ==========
    fig, ax = plt.subplots(figsize=(14, 7))
    
    duty1 = scenario1['duty_avg'].reset_index()
    duty1.columns = ['node', s1['label']]
    duty2 = scenario2['duty_avg'].reset_index()
    duty2.columns = ['node', s2['label']]
    
    duty_merged = pd.merge(duty1, duty2, on='node', how='outer').fillna(0)
    duty_merged = duty_merged.sort_values('node')
    
    x = range(len(duty_merged))
    width = 0.35
    
    ax.bar([i - width/2 for i in x], duty_merged[s1['label']], width,
           label=s1['label'], color='orange', edgecolor='black', linewidth=0.5)
    ax.bar([i + width/2 for i in x], duty_merged[s2['label']], width,
           label=s2['label'], color='purple', edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Node ID', fontsize=12)
    ax.set_ylabel('Duty Cycle (%)', fontsize=12)
    ax.set_title('Radio Duty Cycle Comparison per Node', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(duty_merged['node'].astype(int))
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(charts_dir / '4_duty_cycle_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # ========== 5. NODE LIFETIME COMPARISON ==========
    if len(scenario1['dead']) > 0 and len(scenario2['dead']) > 0:
        fig, ax = plt.subplots(figsize=(14, 7))
        
        dead1 = scenario1['dead'][['node', 'alive']].copy()
        dead1.columns = ['node', s1['label']]
        dead2 = scenario2['dead'][['node', 'alive']].copy()
        dead2.columns = ['node', s2['label']]
        
        dead_merged = pd.merge(dead1, dead2, on='node', how='outer').fillna(0)
        dead_merged = dead_merged.sort_values('node')
        
        x = range(len(dead_merged))
        width = 0.35
        
        ax.bar([i - width/2 for i in x], dead_merged[s1['label']], width,
               label=s1['label'], color='teal', edgecolor='black', linewidth=0.5)
        ax.bar([i + width/2 for i in x], dead_merged[s2['label']], width,
               label=s2['label'], color='crimson', edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Node ID', fontsize=12)
        ax.set_ylabel('Lifetime (seconds)', fontsize=12)
        ax.set_title('Node Lifetime Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(dead_merged['node'].astype(int))
        ax.legend(fontsize=11)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(charts_dir / '5_lifetime_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # ========== 6. COMPARISON SUMMARY TABLE ==========
    summary_df = pd.DataFrame([s1, s2])
    summary_csv = output_dir / 'comparison_summary.csv'
    summary_df.to_csv(summary_csv, index=False, encoding='utf-8-sig')
    
    print(f"\n📊 Comparison Summary:")
    print(summary_df.to_string(index=False))
    print(f"\n✅ Saved comparison charts to: {charts_dir}")
    print(f"✅ Saved comparison CSV to: {summary_csv}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python compare_scenarios.py <log1> <log2> [label1] [label2]")
        print("Example: python compare_scenarios.py normal.log vampire.log 'Normal' 'Vampire Attack'")
        sys.exit(1)
    
    log1 = sys.argv[1]
    log2 = sys.argv[2]
    label1 = sys.argv[3] if len(sys.argv) > 3 else "Scenario 1"
    label2 = sys.argv[4] if len(sys.argv) > 4 else "Scenario 2"
    
    print(f"Loading {label1}: {log1}")
    scenario1 = load_scenario(log1, label1)
    
    print(f"Loading {label2}: {log2}")
    scenario2 = load_scenario(log2, label2)
    
    output_dir = Path(log1).parent.parent / 'results'
    output_dir.mkdir(exist_ok=True)
    
    print("\n🔍 Comparing scenarios...")
    compare_scenarios(scenario1, scenario2, output_dir)
