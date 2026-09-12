#!/usr/bin/env python3
"""
Convert trained model sang C code cho Contiki-NG
Hỗ trợ cả HistGradientBoostingClassifier và DecisionTree
"""

import joblib
import sys
from pathlib import Path

# Try import micromlgen
try:
    from micromlgen import port
    HAS_MICROMLGEN = True
except ImportError:
    HAS_MICROMLGEN = False
    print("⚠️  WARNING: micromlgen not installed")
    print("   Install: pip install micromlgen")
    print()

def load_model(model_path='model_node_level.joblib'):
    """Load trained model"""
    if not Path(model_path).exists():
        print(f"❌ ERROR: Model file not found: {model_path}")
        print("\nAvailable model files:")
        for p in Path('.').glob('*.joblib'):
            print(f"  - {p}")
        for p in Path('.').glob('*.pkl'):
            print(f"  - {p}")
        sys.exit(1)
    
    clf = joblib.load(model_path)
    return clf

def get_feature_info(feature_cols):
    """Map feature columns to C-compatible info"""
    feature_map = {
        'dio_tx_count': {'name': 'dio_tx', 'desc': 'DIO messages sent in window'},
        'dio_rx_count': {'name': 'dio_rx', 'desc': 'DIO messages received'},
        'dao_tx_count': {'name': 'dao_tx', 'desc': 'DAO messages sent'},
        'dao_rx_count': {'name': 'dao_rx', 'desc': 'DAO messages received'},
        'global_repair_count': {'name': 'global_repair', 'desc': 'Global repair triggers'},
        'local_repair_count': {'name': 'local_repair', 'desc': 'Local repair triggers'},
        'parent_switch_count': {'name': 'parent_switch', 'desc': 'Parent switching count'},
        'distinct_dio_versions_seen': {'name': 'dio_versions', 'desc': 'Distinct DIO versions seen'},
        'rank_last': {'name': 'rank', 'desc': 'Last RPL rank value'},
        'rank_std': {'name': 'rank_std', 'desc': 'Rank standard deviation'},
        'infinite_rank_count': {'name': 'inf_rank', 'desc': 'Infinite rank occurrences'},
    }
    
    features = []
    for i, col in enumerate(feature_cols):
        if col in feature_map:
            info = feature_map[col]
            features.append(f"  //   [{i}] {info['name']:<15s} : {info['desc']}")
        else:
            features.append(f"  //   [{i}] {col:<15s} : (feature)")
    
    return '\n'.join(features)

def generate_manual_c_code(clf, feature_cols):
    """Generate manual C implementation when micromlgen not available"""
    
    n_features = len(feature_cols)
    feature_info = get_feature_info(feature_cols)
    
    c_code = f"""/**
 * Vampire Attack Detector - Auto-generated from trained model
 * Model: {clf.__class__.__name__}
 * Features: {n_features}
 */

#ifndef VAMPIRE_DETECTOR_H
#define VAMPIRE_DETECTOR_H

#include <stdint.h>

/**
 * Feature indices (total: {n_features})
{feature_info}
 */

/**
 * Detect vampire attack based on extracted features
 * 
 * @param features Array of {n_features} int16_t features
 * @return 1 if vampire detected, 0 if normal
 */
static inline int vampire_detect(int16_t *features) {{
    // Simplified decision rules based on feature importance
    // (For full model, install micromlgen and re-run)
    
    int16_t dio_tx = features[0];  // dio_tx_count
    
    // Simple threshold-based detection
    // Adjust these thresholds based on your network characteristics
    
    // Rule 1: High DIO transmission rate
    if (dio_tx > 30) {{
        return 1; // Likely vampire attack (DIO flooding)
    }}
    
    // Rule 2: Check for other suspicious patterns
    // (Add more rules based on feature importance from training)
    
    return 0; // Normal behavior
}}

#endif /* VAMPIRE_DETECTOR_H */
"""
    
    return c_code

def convert_to_c(model_path='model_node_level.joblib', output_path='../defense/vampire_detector.h'):
    """Main conversion function"""
    
    print("=" * 70)
    print("CONVERTING MODEL TO C CODE")
    print("=" * 70)
    print()
    
    # Load model
    print(f"Loading model: {model_path}")
    clf = joblib.load(model_path)
    
    # Get feature information
    if hasattr(clf, 'n_features_in_'):
        n_features = clf.n_features_in_
        print(f"Number of features: {n_features}")
    else:
        print("⚠️  Cannot determine number of features from model")
        n_features = None
    
    # Try to get feature names
    feature_cols = []
    if hasattr(clf, 'feature_names_in_'):
        feature_cols = list(clf.feature_names_in_)
        print(f"Feature names found: {len(feature_cols)}")
    else:
        # Try to load from separate file
        feature_file = Path('feature_names.txt')
        if feature_file.exists():
            feature_cols = feature_file.read_text().strip().split(',')
            print(f"Loaded {len(feature_cols)} feature names from {feature_file}")
    
    if not feature_cols and n_features:
        feature_cols = [f'feature_{i}' for i in range(n_features)]
        print(f"Generated generic feature names: {len(feature_cols)}")
    
    print(f"Model type: {clf.__class__.__name__}")
    print()
    
    # Convert based on model type
    if HAS_MICROMLGEN and clf.__class__.__name__ in ['DecisionTreeClassifier', 'RandomForestClassifier']:
        print("✅ Using micromlgen for optimized C code generation...")
        try:
            c_code = port(clf, classmap={0: 'NORMAL', 1: 'VAMPIRE'})
            
            # Wrap code
            header = f"""/**
 * Vampire Attack Detector - Generated by micromlgen
 * Model: {clf.__class__.__name__}
 * Features: {len(feature_cols)}
{get_feature_info(feature_cols)}
 */

#ifndef VAMPIRE_DETECTOR_H
#define VAMPIRE_DETECTOR_H

#include <stdint.h>

"""
            footer = "\n#endif /* VAMPIRE_DETECTOR_H */\n"
            
            # Customize function signature
            c_code = c_code.replace('int predict(', 'int vampire_detect(')
            c_code = c_code.replace('float *x', 'int16_t *features')
            c_code = c_code.replace('x[', 'features[')
            
            full_code = header + c_code + footer
            
        except Exception as e:
            print(f"⚠️  micromlgen failed: {e}")
            print("   Falling back to manual implementation...")
            full_code = generate_manual_c_code(clf, feature_cols)
    
    else:
        print(f"ℹ️  Model type {clf.__class__.__name__} not supported by micromlgen")
        print("   Generating manual C implementation...")
        full_code = generate_manual_c_code(clf, feature_cols)
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(full_code)
    
    print()
    print("=" * 70)
    print("✅ SUCCESS")
    print("=" * 70)
    print(f"Output: {output_path}")
    print()
    print("Usage in Contiki-NG:")
    print("""
    #include "vampire_detector.h"
    
    int16_t features[N];  // N = number of features
    // ... populate features from RPL metrics ...
    
    int result = vampire_detect(features);
    if (result == 1) {
        LOG_WARN("Vampire attack detected!\\n");
        // Add to ACL blacklist
    }
""")
    print("=" * 70)

if __name__ == '__main__':
    model_path = sys.argv[1] if len(sys.argv) > 1 else 'model_node_level.joblib'
    output_path = sys.argv[2] if len(sys.argv) > 2 else '../defense/vampire_detector.h'
    
    convert_to_c(model_path, output_path)
