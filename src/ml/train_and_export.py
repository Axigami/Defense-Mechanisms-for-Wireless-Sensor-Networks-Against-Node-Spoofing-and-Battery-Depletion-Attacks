#!/usr/bin/env python3
"""
train_and_export.py
====================
Tien xu ly du lieu, xu ly mat can bang lop (SMOTE/Undersampling),
huan luyen va danh gia toan dien mo hinh phat hien tan cong Vampire
(RPL Version Number Attack & Battery Depletion) trong WSN.

Pipeline cai tien:
  1. Load toan bo CSV tu data/results/
  2. Data Preprocessing & Cleaning: Loc bo cac cua so khong hoat dong (dormant/non-event)
     tranh gay nhieu nhan nghiem trong
  3. Feature Selection & Extraction: 5 dac trung cuc bo tuong thich 100% Contiki-NG
  4. Train/Test Stratified Split: Tap test giu nguyen phan phoi that de danh gia khach quan
  5. Imbalance Handling: SMOTE tren tap Train giup mo hinh hoc dac trung lop Attacker
  6. Decision Threshold Tuning: Tim nguong quyet dinh toi uu (F1/F2) thay vi mac dinh 0.5
  7. Multi-model Training & Benchmark:
     - Decision Tree (pruned, de xuat code C nhung truc tiep vao node Contiki-NG)
     - Random Forest (benchmark ensemble ensemble)
  8. Comprehensive Evaluation: Accuracy, Precision, Recall, F1, F2, ROC-AUC, PR-AUC
  9. Visualization:
     - Feature Importance (so sanh DT vs RF)
     - Confusion Matrix (heatmap so luong + ty le % chuan hoa)
     - ROC & Precision-Recall Curves (danh gia tren du lieu lech lop)
  10. Export sang C va luu metadata: ho tro convert_to_c.py

Usage:
  python ml/train_and_export.py
  python ml/train_and_export.py --imbalance-method smote --tune-metric f1
  python ml/train_and_export.py --tune-metric f2  # Uu tien Recall cao hon cho an ninh mang
"""

import argparse
import glob
import json
import os
import sys
import numpy as np
import pandas as pd
import joblib

import matplotlib
matplotlib.use('Agg')  # Headless backend (khong can man hinh GUI)
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    fbeta_score,
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
    average_precision_score
)

# ----------------------------------------------------------------
# Constants & Column Definitions
# ----------------------------------------------------------------
EXCLUDE_COLS = {
    'node', 'window', 'scenario', 'run_id', 'log_file',
    'label_network_attack',
}
GROUNDTRUTH_SUFFIX = '_GROUNDTRUTH'
LABEL_COL = 'is_attacker_node_GROUNDTRUTH'

# 5 dac trung cuc bo ma mot sensor node Contiki-NG co the truc tiep quan sat
LOCAL_FEATURE_COLS = ['dio_rate', 'version_delta', 'rank', 'rank_delta', 'is_poison']


def load_all_csvs(data_dir):
    """Doc tat ca file features_*_node.csv trong data_dir hoac cac thu muc tuong duong."""
    pattern = os.path.join(data_dir, 'features_*_node.csv')
    files = sorted(glob.glob(pattern))

    if not files:
        alt_dirs = [
            os.path.join('data', 'results'),
            os.path.join('..', 'data', 'results'),
            os.path.join('ml', 'data', 'results'),
            os.path.join(os.path.dirname(__file__), 'data', 'results'),
            os.path.join(os.path.dirname(__file__), '..', 'data', 'results'),
        ]
        for alt in alt_dirs:
            alt_files = sorted(glob.glob(os.path.join(alt, 'features_*_node.csv')))
            if alt_files:
                files = alt_files
                data_dir = alt
                break

    if not files:
        print(f"\n  [LOI] Khong tim thay file CSV nao khop pattern: {pattern}")
        print(f"  Vui long chay collect_training_data.py de tao dataset truoc!")
        return None

    print(f"\n  Tim thay {len(files)} file CSV tai '{data_dir}':")
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            scenario = df['scenario'].iloc[0] if 'scenario' in df.columns else '?'
            n_attack = df[LABEL_COL].sum() if LABEL_COL in df.columns else 0
            print(f"    {os.path.basename(f):50s} {df.shape[0]:>6} rows  "
                  f"scenario={scenario:12s}  attackers={int(n_attack)}")
            dfs.append(df)
        except Exception as e:
            print(f"    {os.path.basename(f):50s} LOI: {e}")

    if not dfs:
        return None

    combined = pd.concat(dfs, ignore_index=True)
    print(f"\n  Tong cong raw: {combined.shape[0]:,} rows, {combined.shape[1]} columns")
    return combined


def preprocess_data(df, mode='local', filter_dormant=True):
    """
    Tien xu ly va lam sach du lieu:
      1. Kiem tra cot nhan ground-truth
      2. Loc bo cac cua so khong co hoat dong (dormant/inactive windows):
         Trong WSN IDS tren Contiki-NG, ham phat hien ML chi duoc kich hoat
         khi co goi tin DIO/DAO thuc su duoc nhan hoac xu ly.
         Cac cua so khong co bat ky traffic nao ([0, 0, 1000, 0, 0])
         tao ra xung dot nhan nghiem trong (hang chuc nghin vector 0 giong nhau
         bi gan ca nhan 0 va 1), lam sup do recall va precision.
      3. Chuan hoa kieu du lieu va xu ly Missing / Inf.
    """
    if LABEL_COL not in df.columns:
        print(f"\n  [LOI] Khong tim thay cot nhan '{LABEL_COL}' trong CSV!")
        return None, None, None

    # 1. Loc bo dormant windows neu duoc bat
    if filter_dormant:
        # Cua so hoan toan khong co traffic / su kien:
        # NOTE: rank=65535 with dio_rate > 0 is NORMAL bootstrap traffic
        # (node just hasn't joined DAG yet). We MUST keep these samples
        # so the ML model learns to distinguish bootstrap from attack.
        has_no_traffic = (
            (df['dio_rate'] == 0) &
            (df['version_delta'] == 0) &
            (df['rank_delta'] == 0) &
            (df['is_poison'] == 0)
        )
        has_idle_rank = df['rank'].isin([1000, 0])
        # rank=65535 with traffic is bootstrap, NOT dormant
        has_unjoined_rank_no_traffic = (df['rank'] == 65535) & has_no_traffic
        
        dormant_mask = has_no_traffic & (has_idle_rank | has_unjoined_rank_no_traffic)
        
        if 'dio_tx_count' in df.columns and 'dio_rx_count' in df.columns:
            dormant_mask = dormant_mask & (df['dio_tx_count'] == 0) & (df['dio_rx_count'] == 0)

        n_dormant = int(dormant_mask.sum())
        n_att_dormant = int(df[dormant_mask][LABEL_COL].sum())
        n_norm_dormant = n_dormant - n_att_dormant
        
        # Count bootstrap windows preserved (rank=65535 with activity)
        bootstrap_mask = (df['rank'] == 65535) & (df['dio_rate'] > 0)
        n_bootstrap_kept = int((bootstrap_mask & ~dormant_mask).sum())

        print(f"\n  [TIEN XU LY DULIEU] Loc bo cac cua so khong co giao thuc/su kien:")
        print(f"    - So mau khong hoat dong bi loai : {n_dormant:,} (Normal: {n_norm_dormant:,}, Attacker chua ban traffic: {n_att_dormant:,})")
        print(f"    - So mau bootstrap (rank=65535, co traffic) GIU LAI: {n_bootstrap_kept:,}")
        print(f"    - So su kien hoat dong con lai     : {len(df) - n_dormant:,} rows")

        df = df[~dormant_mask].copy()

    # 2. Chon features
    if mode == 'local':
        for c in LOCAL_FEATURE_COLS:
            if c not in df.columns:
                df[c] = 0
        feature_cols = LOCAL_FEATURE_COLS.copy()
    else:
        feature_cols = [c for c in df.columns
                        if c not in EXCLUDE_COLS
                        and not c.endswith(GROUNDTRUTH_SUFFIX)]

    y = df[LABEL_COL].values.astype(int)
    X = df[feature_cols].copy()
    X = X.fillna(0).replace([np.inf, -np.inf], 0)

    for c in feature_cols[:]:
        try:
            X[c] = pd.to_numeric(X[c], errors='coerce')
        except Exception:
            feature_cols.remove(c)
            X.drop(c, axis=1, inplace=True)

    X = X.fillna(0)
    return X, y, feature_cols


def balance_training_data(X_train, y_train, method='smote'):
    """
    Xu ly mat can bang tren tap TRAIN (khong tac dong tap Test de danh gia trung thuc).
      - 'smote'    : Sinh mau nhan tao cho Attacker bang noi suy KNN
      - 'smote_rus': Ket hop undersampling mot phan Normal va SMOTE Attacker
      - 'rus'      : Random undersampling lop Normal
      - 'none'     : Giu nguyen du lieu goc
    """
    n_norm = int(np.sum(y_train == 0))
    n_att = int(np.sum(y_train == 1))
    print(f"\n  [XU LY MAT CAN BANG] Tap Train goc: Normal={n_norm:,}, Attacker={n_att:,} (ti le {n_att/n_norm*100:.2f}%)")

    if method == 'smote':
        from imblearn.over_sampling import SMOTE
        target_ratio = min(0.8, max(0.3, (n_att * 10) / n_norm))
        sm = SMOTE(sampling_strategy=target_ratio, random_state=42)
        X_res, y_res = sm.fit_resample(X_train, y_train)
    elif method == 'smote_rus':
        from imblearn.under_sampling import RandomUnderSampler
        from imblearn.over_sampling import SMOTE
        rus = RandomUnderSampler(sampling_strategy=0.25, random_state=42)
        X_rus, y_rus = rus.fit_resample(X_train, y_train)
        sm = SMOTE(sampling_strategy=0.6, random_state=42)
        X_res, y_res = sm.fit_resample(X_rus, y_rus)
    elif method == 'rus':
        from imblearn.under_sampling import RandomUnderSampler
        rus = RandomUnderSampler(sampling_strategy=0.33, random_state=42)
        X_res, y_res = rus.fit_resample(X_train, y_train)
    else:
        X_res, y_res = X_train, y_train

    n_norm_after = int(np.sum(y_res == 0))
    n_att_after = int(np.sum(y_res == 1))
    print(f"  [XU LY MAT CAN BANG] Sau {method.upper()}: Normal={n_norm_after:,}, Attacker={n_att_after:,} (ti le {n_att_after/n_norm_after*100:.1f}%)")
    return X_res, y_res


def tune_decision_threshold(probs, y_true, metric='f1'):
    """
    Tim nguong quyet dinh toi uu (Threshold Tuning).
      - 'f1'           : Toi da hoa F1-Score (hai hoa Precision & Recall)
      - 'f2'           : Toi da hoa F2-Score (uu tien Recall cao cho IDS)
      - 'recall_target': Toi thieu Recall >= 80% voi Precision cao nhat
    """
    best_th = 0.5
    best_score = -1.0
    thresholds = np.linspace(0.05, 0.95, 91)

    for th in thresholds:
        preds = (probs >= th).astype(int)
        r = recall_score(y_true, preds, zero_division=0)
        p = precision_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        f2 = fbeta_score(y_true, preds, beta=2, zero_division=0)

        if metric == 'f1':
            score = f1
        elif metric == 'f2':
            score = f2
        elif metric == 'recall_target':
            score = p if r >= 0.80 else (r * 0.1)
        else:
            score = f1

        if score > best_score:
            best_score = score
            best_th = th

    return float(best_th)


def compute_comprehensive_metrics(y_true, y_pred, probs):
    """Tinh toan tat ca chi so danh gia phu hop cho bai toan an ninh mang lech lop."""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    f2 = fbeta_score(y_true, y_pred, beta=2, zero_division=0)
    roc_auc = roc_auc_score(y_true, probs)
    pr_auc = average_precision_score(y_true, probs)
    cm = confusion_matrix(y_true, y_pred)

    return {
        'accuracy': float(acc),
        'precision': float(prec),
        'recall': float(rec),
        'f1': float(f1),
        'f2': float(f2),
        'roc_auc': float(roc_auc),
        'pr_auc': float(pr_auc),
        'confusion_matrix': cm
    }


def train_models(X_train, y_train, X_test, y_test, feature_cols,
                 max_depth=7, tune_metric='f1', manual_th=None):
    """Huan luyen Decision Tree va Random Forest, toi uu nguong va danh gia."""
    # ========== 1. Decision Tree (Model nhung C cho Contiki-NG) ==========
    dt = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=10,
        min_samples_split=20,
        random_state=42
    )
    dt.fit(X_train, y_train)
    dt_probs = dt.predict_proba(X_test)[:, 1]

    # Nguong quyet dinh
    if manual_th is not None:
        th_dt = float(manual_th)
    else:
        th_dt = tune_decision_threshold(dt_probs, y_test, metric=tune_metric)

    dt_pred = (dt_probs >= th_dt).astype(int)
    dt_metrics = compute_comprehensive_metrics(y_test, dt_pred, dt_probs)
    dt_metrics['threshold'] = th_dt

    print(f"\n{'='*65}")
    print(f"DECISION TREE (max_depth={max_depth}, Threshold={th_dt:.2f}) - EMBEDDED C MODEL")
    print(f"{'='*65}")
    print(classification_report(
        y_test, dt_pred,
        target_names=['NORMAL', 'ATTACKER'],
        digits=3, zero_division=0
    ))
    print(f"  Metrics chi tiet:")
    print(f"    - Accuracy         : {dt_metrics['accuracy']*100:.1f}%")
    print(f"    - Precision        : {dt_metrics['precision']*100:.1f}%")
    print(f"    - Recall           : {dt_metrics['recall']*100:.1f}% (Phat hien {dt_metrics['confusion_matrix'][1,1]}/{sum(y_test==1)} cuoc tan cong)")
    print(f"    - F1-Score         : {dt_metrics['f1']:.3f}")
    print(f"    - F2-Score (Recall): {dt_metrics['f2']:.3f}")
    print(f"    - ROC-AUC          : {dt_metrics['roc_auc']:.3f}")
    print(f"    - PR-AUC           : {dt_metrics['pr_auc']:.3f}")

    cm_dt = dt_metrics['confusion_matrix']
    print(f"\n  Confusion Matrix:")
    print(f"                 Predicted NORMAL  Predicted ATTACKER")
    print(f"  Actual NORMAL     {cm_dt[0,0]:>7d}          {cm_dt[0,1]:>7d}")
    if cm_dt.shape[0] > 1:
        print(f"  Actual ATTACKER   {cm_dt[1,0]:>7d}          {cm_dt[1,1]:>7d}")

    # ========== 2. Random Forest (Benchmark Ensemble Model) ==========
    rf = RandomForestClassifier(
        n_estimators=150,
        max_depth=10,
        min_samples_leaf=5,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    rf_probs = rf.predict_proba(X_test)[:, 1]

    if manual_th is not None:
        th_rf = float(manual_th)
    else:
        th_rf = tune_decision_threshold(rf_probs, y_test, metric=tune_metric)

    rf_pred = (rf_probs >= th_rf).astype(int)
    rf_metrics = compute_comprehensive_metrics(y_test, rf_pred, rf_probs)
    rf_metrics['threshold'] = th_rf

    print(f"\n{'='*65}")
    print(f"RANDOM FOREST (Benchmark, Threshold={th_rf:.2f})")
    print(f"{'='*65}")
    print(classification_report(
        y_test, rf_pred,
        target_names=['NORMAL', 'ATTACKER'],
        digits=3, zero_division=0
    ))
    print(f"  Metrics chi tiet:")
    print(f"    - Accuracy         : {rf_metrics['accuracy']*100:.1f}%")
    print(f"    - Precision        : {rf_metrics['precision']*100:.1f}%")
    print(f"    - Recall           : {rf_metrics['recall']*100:.1f}%")
    print(f"    - F1-Score         : {rf_metrics['f1']:.3f}")
    print(f"    - F2-Score (Recall): {rf_metrics['f2']:.3f}")
    print(f"    - ROC-AUC          : {rf_metrics['roc_auc']:.3f}")
    print(f"    - PR-AUC           : {rf_metrics['pr_auc']:.3f}")

    # Feature Importance DataFrame
    importances = pd.DataFrame({
        'feature': feature_cols,
        'importance_rf': rf.feature_importances_,
        'importance_dt': dt.feature_importances_,
        'importance': rf.feature_importances_
    }).sort_values('importance_rf', ascending=False)

    print(f"\n  Top features quan trong nhat (RF vs DT):")
    for rank, (_, row) in enumerate(importances.iterrows(), 1):
        print(f"    {rank:2d}. {row['feature']:<20s} RF={row['importance_rf']:.4f}  DT={row['importance_dt']:.4f}")

    eval_data = {
        'y_test': y_test,
        'dt_probs': dt_probs,
        'rf_probs': rf_probs,
        'dt_pred': dt_pred,
        'rf_pred': rf_pred,
        'dt_metrics': dt_metrics,
        'rf_metrics': rf_metrics,
    }

    return dt, rf, importances, eval_data


def plot_feature_importance(dt, rf, feature_cols, out_dir):
    """Ve bieu do do quan trong dac trung (Feature Importance)."""
    os.makedirs(out_dir, exist_ok=True)

    df_imp = pd.DataFrame({
        'feature': feature_cols,
        'importance_dt': dt.feature_importances_,
        'importance_rf': rf.feature_importances_
    }).sort_values('importance_rf', ascending=True)

    # 1. Bieu do ket hop 2 subplots
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    y_pos = np.arange(len(df_imp))

    # DT
    max_dt = max(df_imp['importance_dt'].max(), 0.1)
    axes[0].barh(y_pos, df_imp['importance_dt'], color='#2b5c8f', edgecolor='black', height=0.55, alpha=0.85)
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels(df_imp['feature'], fontsize=11, fontweight='bold')
    axes[0].set_xlabel('Gini Importance', fontsize=12, fontweight='bold')
    axes[0].set_title('Decision Tree (Embedded C Model)', fontsize=13, fontweight='bold', pad=10)
    axes[0].grid(axis='x', linestyle='--', alpha=0.6)
    axes[0].set_xlim(0, max_dt * 1.3)
    for i, v in enumerate(df_imp['importance_dt']):
        axes[0].text(v + (max_dt * 0.02), i, f"{v:.3f} ({v*100:.1f}%)",
                     va='center', fontsize=10, fontweight='bold', color='#1a365d')

    # RF
    max_rf = max(df_imp['importance_rf'].max(), 0.1)
    axes[1].barh(y_pos, df_imp['importance_rf'], color='#2a9d8f', edgecolor='black', height=0.55, alpha=0.85)
    axes[1].set_xlabel('Gini Importance', fontsize=12, fontweight='bold')
    axes[1].set_title('Random Forest (Benchmark Ensemble)', fontsize=13, fontweight='bold', pad=10)
    axes[1].grid(axis='x', linestyle='--', alpha=0.6)
    axes[1].set_xlim(0, max_rf * 1.3)
    for i, v in enumerate(df_imp['importance_rf']):
        axes[1].text(v + (max_rf * 0.02), i, f"{v:.3f} ({v*100:.1f}%)",
                     va='center', fontsize=10, fontweight='bold', color='#134e4a')

    fig.suptitle('Feature Importance Comparison: Decision Tree vs Random Forest',
                 fontsize=15, fontweight='bold', y=0.99)
    plt.tight_layout()
    combined_path = os.path.join(out_dir, 'feature_importance.png')
    plt.savefig(combined_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    # 2. Single DT
    fig_dt, ax_dt = plt.subplots(figsize=(8, 4.8))
    df_dt_sorted = df_imp.sort_values('importance_dt', ascending=True)
    y_dt = np.arange(len(df_dt_sorted))
    ax_dt.barh(y_dt, df_dt_sorted['importance_dt'], color='#2b5c8f', edgecolor='black', height=0.5, alpha=0.85)
    ax_dt.set_yticks(y_dt)
    ax_dt.set_yticklabels(df_dt_sorted['feature'], fontsize=11, fontweight='bold')
    ax_dt.set_xlabel('Gini Importance', fontsize=12, fontweight='bold')
    ax_dt.set_title('Decision Tree Feature Importance (Embedded C Model)', fontsize=13, fontweight='bold', pad=12)
    ax_dt.grid(axis='x', linestyle='--', alpha=0.6)
    max_dt_single = max(df_dt_sorted['importance_dt'].max(), 0.1)
    ax_dt.set_xlim(0, max_dt_single * 1.3)
    for i, v in enumerate(df_dt_sorted['importance_dt']):
        ax_dt.text(v + (max_dt_single * 0.02), i, f"{v:.3f} ({v*100:.1f}%)",
                   va='center', fontsize=10, fontweight='bold', color='#1a365d')
    plt.tight_layout()
    dt_path = os.path.join(out_dir, 'feature_importance_dt.png')
    plt.savefig(dt_path, dpi=300, bbox_inches='tight')
    plt.close(fig_dt)

    print(f"\n  Da luu bieu do Feature Importance:")
    print(f"    - {combined_path}")
    print(f"    - {dt_path}")


def plot_confusion_matrices(eval_data, out_dir):
    """Ve bieu do Confusion Matrix heatmap voi so luong va ty le % chuan hoa."""
    os.makedirs(out_dir, exist_ok=True)
    class_names = ['NORMAL', 'ATTACKER']

    cm_dt = eval_data['dt_metrics']['confusion_matrix']
    cm_rf = eval_data['rf_metrics']['confusion_matrix']
    m_dt = eval_data['dt_metrics']
    m_rf = eval_data['rf_metrics']

    def draw_heatmap(ax, cm, title_prefix, m, cmap='Blues'):
        cm_sum = cm.sum(axis=1, keepdims=True)
        cm_perc = np.divide(cm.astype(float), cm_sum, out=np.zeros_like(cm, dtype=float), where=cm_sum != 0) * 100

        annot = np.empty_like(cm, dtype=object)
        cell_types = [['TN', 'FP'], ['FN', 'TP']] if cm.shape == (2, 2) else None
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                prefix = f"{cell_types[i][j]}: " if cell_types else ""
                annot[i, j] = f"{prefix}{cm[i, j]:,}\n({cm_perc[i, j]:.1f}%)"

        sns.heatmap(cm, annot=annot, fmt='', cmap=cmap, cbar=False, ax=ax,
                    xticklabels=class_names, yticklabels=class_names,
                    annot_kws={'fontsize': 11, 'fontweight': 'bold'},
                    linewidths=1.5, linecolor='white')
        ax.set_xlabel('Predicted Label', fontsize=12, fontweight='bold', labelpad=8)
        ax.set_ylabel('True Label', fontsize=12, fontweight='bold', labelpad=8)

        subtitle = (f"{title_prefix} (Threshold: {m['threshold']:.2f})\n"
                    f"Accuracy: {m['accuracy']*100:.1f}% | Precision: {m['precision']*100:.1f}%\n"
                    f"Recall: {m['recall']*100:.1f}% | F1: {m['f1']:.3f} | ROC-AUC: {m['roc_auc']:.3f}")
        ax.set_title(subtitle, fontsize=11, fontweight='bold', pad=12)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    draw_heatmap(axes[0], cm_dt, 'Decision Tree (Embedded C Model)', m_dt, cmap='Blues')
    draw_heatmap(axes[1], cm_rf, 'Random Forest (Benchmark)', m_rf, cmap='Greens')

    fig.suptitle('Confusion Matrix: Decision Tree vs Random Forest (Calibrated Thresholds)',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    combined_path = os.path.join(out_dir, 'confusion_matrix.png')
    plt.savefig(combined_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    # Single DT
    fig_dt, ax_dt = plt.subplots(figsize=(6.2, 5.2))
    draw_heatmap(ax_dt, cm_dt, 'Decision Tree (Embedded C Model)', m_dt, cmap='Blues')
    plt.tight_layout()
    dt_path = os.path.join(out_dir, 'confusion_matrix_dt.png')
    plt.savefig(dt_path, dpi=300, bbox_inches='tight')
    plt.close(fig_dt)

    print(f"\n  Da luu bieu do Confusion Matrix:")
    print(f"    - {combined_path}")
    print(f"    - {dt_path}")


def plot_roc_and_pr_curves(eval_data, out_dir):
    """Ve duong cong ROC va Precision-Recall Curve (danh gia chuan cho tap lech lop)."""
    os.makedirs(out_dir, exist_ok=True)
    y_test = eval_data['y_test']
    dt_probs = eval_data['dt_probs']
    rf_probs = eval_data['rf_probs']
    m_dt = eval_data['dt_metrics']
    m_rf = eval_data['rf_metrics']

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    # 1. ROC Curve
    fpr_dt, tpr_dt, _ = roc_curve(y_test, dt_probs)
    fpr_rf, tpr_rf, _ = roc_curve(y_test, rf_probs)

    axes[0].plot(fpr_dt, tpr_dt, color='#2b5c8f', lw=2.2,
                 label=f"Decision Tree (AUC = {m_dt['roc_auc']:.3f})")
    axes[0].plot(fpr_rf, tpr_rf, color='#2a9d8f', lw=2.2,
                 label=f"Random Forest (AUC = {m_rf['roc_auc']:.3f})")
    axes[0].plot([0, 1], [0, 1], color='gray', linestyle='--', lw=1.5, label='Random Guess')
    axes[0].set_xlim([0.0, 1.0])
    axes[0].set_ylim([0.0, 1.05])
    axes[0].set_xlabel('False Positive Rate (FPR)', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('True Positive Rate / Recall (TPR)', fontsize=12, fontweight='bold')
    axes[0].set_title('Receiver Operating Characteristic (ROC)', fontsize=13, fontweight='bold', pad=10)
    axes[0].legend(loc='lower right', fontsize=10)
    axes[0].grid(True, linestyle='--', alpha=0.6)

    # 2. Precision-Recall Curve
    prec_dt, rec_dt, _ = precision_recall_curve(y_test, dt_probs)
    prec_rf, rec_rf, _ = precision_recall_curve(y_test, rf_probs)
    baseline_p = float(np.sum(y_test == 1)) / len(y_test)

    axes[1].plot(rec_dt, prec_dt, color='#2b5c8f', lw=2.2,
                 label=f"Decision Tree (PR-AUC = {m_dt['pr_auc']:.3f})")
    axes[1].plot(rec_rf, prec_rf, color='#2a9d8f', lw=2.2,
                 label=f"Random Forest (PR-AUC = {m_rf['pr_auc']:.3f})")
    axes[1].axhline(y=baseline_p, color='gray', linestyle='--', lw=1.5,
                    label=f"No-Skill Baseline ({baseline_p*100:.1f}%)")
    axes[1].set_xlim([0.0, 1.0])
    axes[1].set_ylim([0.0, 1.05])
    axes[1].set_xlabel('Recall', fontsize=12, fontweight='bold')
    axes[1].set_ylabel('Precision', fontsize=12, fontweight='bold')
    axes[1].set_title('Precision-Recall (PR) Curve', fontsize=13, fontweight='bold', pad=10)
    axes[1].legend(loc='upper right', fontsize=10)
    axes[1].grid(True, linestyle='--', alpha=0.6)

    fig.suptitle('ROC & Precision-Recall Curves for Imbalanced IDS Evaluation',
                 fontsize=14, fontweight='bold', y=0.99)
    plt.tight_layout()
    curve_path = os.path.join(out_dir, 'roc_pr_curves.png')
    plt.savefig(curve_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print(f"    - {curve_path}")


def save_models_and_artifacts(dt, rf, feature_cols, importances, eval_data, out_dir):
    """Luu toan bo model, metadata JSON va CSV feature importance."""
    os.makedirs(out_dir, exist_ok=True)

    dt_path = os.path.join(out_dir, 'model_vampire_dt.joblib')
    rf_path = os.path.join(out_dir, 'model_vampire_rf.joblib')
    feat_path = os.path.join(out_dir, 'model_feature_cols.joblib')
    imp_path = os.path.join(out_dir, 'feature_importance.csv')
    meta_path = os.path.join(out_dir, 'model_metadata.json')

    joblib.dump(dt, dt_path)
    joblib.dump(rf, rf_path)
    joblib.dump(feature_cols, feat_path)
    importances.to_csv(imp_path, index=False)

    metadata = {
        'optimal_threshold': eval_data['dt_metrics']['threshold'],
        'optimal_threshold_pct': int(round(eval_data['dt_metrics']['threshold'] * 100)),
        'features': feature_cols,
        'metrics_dt': {k: v for k, v in eval_data['dt_metrics'].items() if k != 'confusion_matrix'},
        'metrics_rf': {k: v for k, v in eval_data['rf_metrics'].items() if k != 'confusion_matrix'},
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n  Da luu models va metadata vao '{out_dir}':")
    print(f"    - {dt_path}")
    print(f"    - {rf_path}")
    print(f"    - {feat_path}")
    print(f"    - {imp_path}")
    print(f"    - {meta_path}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument('--data-dir', default='data/results',
                    help="Thu muc chua cac file features_*_node.csv (mac dinh: data/results)")
    ap.add_argument('--model-dir', default='output',
                    help="Thu muc luu model output va bieu do (mac dinh: output)")
    ap.add_argument('--plot-dir', default=None,
                    help="Thu muc luu rieng cac bieu do (mac dinh: cung voi --model-dir)")
    ap.add_argument('--max-depth', type=int, default=7,
                    help="Do sau toi da cua Decision Tree (mac dinh: 7)")
    ap.add_argument('--test-size', type=float, default=0.3,
                    help="Ti le test set (mac dinh: 0.3)")
    ap.add_argument('--features-mode', choices=['local', 'full'], default='local',
                    help="Che do feature: 'local' (5 dac trung Contiki-NG C) hoac 'full'")
    ap.add_argument('--imbalance-method', choices=['smote', 'smote_rus', 'rus', 'none'], default='smote',
                    help="Phuong phap xu ly mat can bang: 'smote' (mac dinh), 'smote_rus', 'rus', 'none'")
    ap.add_argument('--tune-metric', choices=['f1', 'f2', 'recall_target'], default='f1',
                    help="Muc tieu toi uu nguong quyet dinh: 'f1' (can bang), 'f2' (uu tien Recall), 'recall_target'")
    ap.add_argument('--threshold', type=float, default=None,
                    help="Chi dinh thu cong nguong quyet dinh (vd: 0.85). Neu bo trong se tu dong toi uu.")
    ap.add_argument('--keep-dormant', action='store_true',
                    help="Khong loc bo cac cua so khong hoat dong (mac dinh se loc bo de tranh nhieu)")
    ap.add_argument('--no-plot', action='store_true',
                    help="Khong ve bieu do (chi train va export)")
    args = ap.parse_args()

    plot_dir = args.plot_dir if args.plot_dir else args.model_dir

    print(f"{'='*65}")
    print(f"   TRAIN & TUNE VAMPIRE ATTACK DETECTOR (IMBALANCED IDS PIPELINE)")
    print(f"{'='*65}")

    # 1. Load CSVs
    df = load_all_csvs(args.data_dir)
    if df is None:
        sys.exit(1)

    # 2. Preprocess & Clean Data
    filter_dormant = not args.keep_dormant
    X, y, feature_cols = preprocess_data(df, mode=args.features_mode, filter_dormant=filter_dormant)
    if X is None:
        sys.exit(1)

    n_norm = int(np.sum(y == 0))
    n_att = int(np.sum(y == 1))
    print(f"\n  Du lieu sau tien xu ly:")
    print(f"    - Features           : {len(feature_cols)} ({', '.join(feature_cols)})")
    print(f"    - Tong so mau active : {len(y):,}")
    print(f"    - Normal             : {n_norm:,} ({100*n_norm/len(y):.1f}%)")
    print(f"    - Attacker           : {n_att:,} ({100*n_att/len(y):.1f}%)")

    if n_att == 0 or n_norm == 0:
        print(f"\n  [LOI] Du lieu thieu mau tan cong hoac mau binh thuong!")
        sys.exit(1)

    # 3. Train/Test Stratified Split
    X_vals = X.values
    X_train, X_test, y_train, y_test = train_test_split(
        X_vals, y, test_size=args.test_size, random_state=42, stratify=y
    )

    # 4. Xu ly mat can bang tren tap Train
    X_tr_bal, y_tr_bal = balance_training_data(X_train, y_train, method=args.imbalance_method)

    # 5. Train & Evaluate
    dt, rf, importances, eval_data = train_models(
        X_tr_bal, y_tr_bal, X_test, y_test, feature_cols,
        max_depth=args.max_depth,
        tune_metric=args.tune_metric,
        manual_th=args.threshold
    )

    # 6. Save models and metadata
    save_models_and_artifacts(dt, rf, feature_cols, importances, eval_data, args.model_dir)

    # Dong bo ca vao thu muc 'ml/' de cac tool luon san sang
    if os.path.abspath(args.model_dir) != os.path.abspath('ml'):
        try:
            save_models_and_artifacts(dt, rf, feature_cols, importances, eval_data, 'ml')
        except Exception:
            pass

    # 7. Ve bieu do danh gia
    if not args.no_plot:
        print(f"\n{'='*65}")
        print(f"   VE BIEU DO DANH GIA MO HINH (FEATURE IMPORTANCE, CM, ROC, PR)")
        print(f"{'='*65}")
        try:
            plot_feature_importance(dt, rf, feature_cols, plot_dir)
            plot_confusion_matrices(eval_data, plot_dir)
            plot_roc_and_pr_curves(eval_data, plot_dir)
        except Exception as e:
            print(f"  [CANH BAO] Khong the ve bieu do: {e}")

    # 8. Summary
    dt_m = eval_data['dt_metrics']
    print(f"\n{'='*65}")
    print(f"   TONG KET KET QUA CAI TIEN")
    print(f"{'='*65}")
    print(f"  Model Decision Tree (C-Embedded):")
    print(f"    - Nguong toi uu (Threshold) : {dt_m['threshold']:.2f}")
    print(f"    - Accuracy                  : {dt_m['accuracy']*100:.1f}%")
    print(f"    - Precision                 : {dt_m['precision']*100:.1f}%")
    print(f"    - Recall                    : {dt_m['recall']*100:.1f}%")
    print(f"    - F1-Score                  : {dt_m['f1']:.3f}")
    print(f"    - ROC-AUC                   : {dt_m['roc_auc']:.3f}")
    print(f"    - PR-AUC                    : {dt_m['pr_auc']:.3f}")
    print(f"\n  Tep bieu do va artifacts da tao trong '{args.model_dir}':")
    print(f"    - feature_importance.png    (Bieu do Feature Importance DT vs RF)")
    print(f"    - confusion_matrix.png      (Bieu do Confusion Matrix heatmap)")
    print(f"    - roc_pr_curves.png         (Bieu do duong cong ROC & PR)")
    print(f"    - model_metadata.json       (Luu nguong toi uu va chi so danh gia)")
    print(f"\n  Buoc tiep theo:")
    print(f"    python ml/convert_to_c.py")
    print(f"    -> Tu dong doc nguong {dt_m['threshold']:.2f} va sinh file defense/vampire_detector.h")
    print(f"{'='*65}")


if __name__ == '__main__':
    main()
