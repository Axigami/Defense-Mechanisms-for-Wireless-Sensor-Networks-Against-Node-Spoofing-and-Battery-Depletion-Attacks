"""
train_baseline_model.py
========================
Doc file feature (xuat ra tu extract_features.py), so sanh voi RULE DON GIAN,
roi train mot model ML lam baseline cho bai toan KHOANH VUNG node tan cong
(node-level) va/hoac phat hien tan cong o muc mang (network-level).

CACH DUNG:
    python3 train_baseline_model.py features_node_level.csv features_network_level.csv

LUU Y: Neu ban chi co 1 lan chay mo phong (1 scenario, 1 node tan cong duy nhat),
ket qua o day CHI MANG TINH MINH HOA / proof-of-concept. De co mot model dung duoc
that su, hay chay nhieu lan mo phong (nhieu seed, nhieu vi tri node tan cong, co ca
kich ban 'normal' rieng) roi gop cac file feature lai (pd.concat) truoc khi chay
script nay.
"""
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score

LEAKAGE_COLS = ['node', 'window', 'scenario', 'run_id', 'is_attacker_node_GROUNDTRUTH']


def rule_baseline_network(net_feat: pd.DataFrame) -> pd.Series:
    """Luat tay khong can ML: nghi tan cong neu co global repair HOAC thay nhieu hon 1
    phien ban DIO trong cung 1 cua so. Dung de CHUNG MINH ML co thuc su can thiet khong."""
    return ((net_feat['total_global_repair'] > 0) | (net_feat['distinct_dio_versions_network'] > 1)).astype(int)


def rule_baseline_localize(node_feat: pd.DataFrame) -> pd.DataFrame:
    """Luat tay de KHOANH VUNG: trong moi cua so co global repair, doan node co
    dio_tx_count CAO NHAT la ke tan cong. Thuong sai vi luc global-repair ca mang
    deu phat DIO nhieu hon binh thuong, khong chi rieng ke tan cong."""
    active = node_feat.groupby('window')['global_repair_count'].sum()
    windows_with_activity = active[active > 0].index
    sub = node_feat[node_feat['window'].isin(windows_with_activity)]
    return sub.loc[sub.groupby('window')['dio_tx_count'].idxmax()]


def train_node_level(node_feat: pd.DataFrame):
    print("\n" + "=" * 70)
    print("BAI TOAN NODE-LEVEL: node nao la ke tan cong?")
    print("=" * 70)

    baseline = rule_baseline_localize(node_feat)
    acc = (baseline['is_attacker_node_GROUNDTRUTH'] == 1).mean()
    print(f"[Rule baseline] argmax(dio_tx_count) trong cua so co global repair: "
          f"doan dung {acc:.1%} tren {len(baseline)} cua so")
    print("  -> Neu so nay THAP, nghia la can ML de hoc pattern phuc tap hon la 'ai noi nhieu nhat'.")

    feature_cols = [c for c in node_feat.columns if c not in LEAKAGE_COLS]
    X = node_feat[feature_cols]
    y = node_feat['is_attacker_node_GROUNDTRUTH']

    if node_feat['run_id'].nunique() > 1:
        # NHIEU lan chay -> split theo NHOM (moi run rieng), tranh leakage giua cac cua so cung 1 run
        from sklearn.model_selection import GroupKFold
        groups = node_feat['run_id']
        gkf = GroupKFold(n_splits=min(5, node_feat['run_id'].nunique()))
        train_idx, test_idx = next(gkf.split(X, y, groups))
        print("[Split] Nhieu run_id -> dung GroupKFold (khong ro ri giua cac lan chay)")
    else:
        # CHI 1 lan chay -> danh split theo THOI GIAN (train qua khu, test tuong lai) de demo
        # KHONG dai dien cho hieu nang that; chi de kiem tra code chay duoc dau cuoi.
        split_w = node_feat['window'].quantile(0.7)
        train_idx = node_feat.index[node_feat['window'] <= split_w]
        test_idx = node_feat.index[node_feat['window'] > split_w]
        print(f"[Split] CHI CO 1 run_id -> tam split theo thoi gian (window <= {split_w:.0f} la train).")
        print("  CANH BAO: day KHONG phai split chuan; chi de minh hoa code hoat dong.")
        print("  Khi co nhieu lan chay that, hay dung GroupKFold theo run_id nhu nhanh code ben tren.")

    Xtr, Xte = X.loc[train_idx], X.loc[test_idx]
    ytr, yte = y.loc[train_idx], y.loc[test_idx]

    clf = HistGradientBoostingClassifier(max_depth=4, class_weight='balanced', random_state=42)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    proba = clf.predict_proba(Xte)[:, 1]

    print(f"\n[ML - HistGradientBoosting] tren {len(Xte)} dong test "
          f"(that su la ke tan cong: {int(yte.sum())} dong)")
    print(classification_report(yte, pred, digits=3, zero_division=0))
    if yte.nunique() > 1:
        print(f"ROC-AUC: {roc_auc_score(yte, proba):.3f}")

    # feature importance qua permutation (on dinh hon voi HGB so voi feature_importances_ mac dinh)
    from sklearn.inspection import permutation_importance
    r = permutation_importance(clf, Xte, yte, n_repeats=10, random_state=42, scoring='f1')
    order = np.argsort(r.importances_mean)[::-1]
    print("\nTop 10 feature quan trong nhat (permutation importance, do bang F1):")
    for i in order[:10]:
        print(f"  {feature_cols[i]:<30s} {r.importances_mean[i]:+.4f}")

    joblib.dump(clf, 'model_node_level.joblib')
    print("\n[OK] Da luu model: model_node_level.joblib")

    # ---- KIEM TRA "FEATURE QUA TOT CO DANG NGO KHONG?" ----
    # Cac feature bat nguon tu goi DU LIEU (tx_count, delivered_count, avg_latency_ms, energy_*)
    # co the chi phan anh viec code tan cong cua BAN log/gui du lieu khac voi node thuong
    # (vd chu ky gui khac nhau), chu KHONG phai ban chat ky thuat tan cong RPL. Neu bo cac cot
    # nay ma diem giam manh, hay nghi lai xem ket qua "tot" ban dau co dang tin khong.
    dataplane_cols = [c for c in ['tx_count', 'delivered_count', 'avg_latency_ms',
                                   'energy_used_sum', 'energy_rate_mj_per_s_mean'] if c in feature_cols]
    if dataplane_cols:
        rpl_only_cols = [c for c in feature_cols if c not in dataplane_cols]
        clf2 = HistGradientBoostingClassifier(max_depth=4, class_weight='balanced', random_state=42)
        clf2.fit(Xtr[rpl_only_cols], ytr)
        pred2 = clf2.predict(Xte[rpl_only_cols])
        print(f"\n[Doi chieu] Neu BO cac cot goc-tu-du-lieu {dataplane_cols}")
        print("  (chi con feature RPL control-plane thuan tuy):")
        print(classification_report(yte, pred2, digits=3, zero_division=0))
        print("  -> Neu diem SUT MANH so voi ket qua o tren, nghia la mot phan ket qua 'tot' ban dau")
        print("     den tu SU KHAC BIET NGAU NHIEN trong cach node tan cong gui/log du lieu (vd chu ky")
        print("     TX khac node thuong), chu KHONG han la 'dau vet' that su cua Version Number Attack.")
        print("     -> Nen kiem tra lai code node tan cong co dang 'lo' theo cach nay khong.")

    return clf, feature_cols


def train_network_level(net_feat: pd.DataFrame):
    print("\n" + "=" * 70)
    print("BAI TOAN NETWORK-LEVEL: mang co dang bi tan cong khong?")
    print("=" * 70)

    if 'label_attack' not in net_feat.columns:
        print("[Bo qua] Khong thay cot 'label_attack' - hay chay extract_features.py voi --scenario truoc.")
        return None, None

    rb = rule_baseline_network(net_feat)
    match = (rb == net_feat['label_attack']).mean()
    print(f"[Rule baseline] 'global_repair>0 OR >1 phien ban DIO' khop {match:.1%} voi nhan "
          f"(tren du lieu chi co 1 kich ban thi day la ty le tu trung voi cach gan nhan, "
          f"can kiem tra lai khi co ca file 'normal' that su).")

    if net_feat['label_attack'].nunique() < 2:
        print("[Dung] Chi co 1 lop nhan duy nhat trong file nay -> KHONG THE train/danh gia phan loai.")
        print("  Day chinh la ly do PHAI chay them kich ban 'normal' rieng (xem phan 2 trong huong dan).")
        return None, None
    # ... (phan train o day tuong tu train_node_level, de trong cho ban tu mo rong
    #      khi da co nhieu run + ca 2 lop nhan)


if __name__ == '__main__':
    node_path = sys.argv[1] if len(sys.argv) > 1 else 'features_node_level.csv'
    net_path = sys.argv[2] if len(sys.argv) > 2 else 'features_network_level.csv'

    node_feat = pd.read_csv(node_path)
    net_feat = pd.read_csv(net_path)

    train_node_level(node_feat)
    train_network_level(net_feat)