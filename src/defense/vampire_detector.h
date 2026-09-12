/**
 * Vampire Attack Detector - Decision Tree Implementation
 * Auto-generated from scikit-learn model
 * 
 * Features:
 *   [0] DIO_rate      : Number of DIO messages in 60s (0-60)
 *   [1] Version_Delta : Version difference from root (0-15)
 *   [2] Rank          : RPL rank value (128-2048)
 * 
 * Returns:
 *   0 = NORMAL node
 *   1 = VAMPIRE attack detected
 */

#ifndef VAMPIRE_DETECTOR_H
#define VAMPIRE_DETECTOR_H

#include <stdint.h>

/**
 * Detect vampire attack based on extracted features
 * 
 * This function implements a decision tree trained offline
 * using scikit-learn and converted to optimized C code.
 * 
 * @param features Array of 3 integer features:
 *                 [0] DIO_rate (0-60)
 *                 [1] Version_Delta (0-15)
 *                 [2] Rank (128-2048)
 * @return 1 if vampire attack detected, 0 if normal
 */
static inline int vampire_detect(int16_t *features) {
    int16_t dio_rate = features[0];
    int16_t version_delta = features[1];
    int16_t rank = features[2];
    
    /* Decision Tree Rules (trained on vampire attack patterns) */
    
    /* Rule 1: High DIO rate với version manipulation */
    if (dio_rate > 30) {
        if (version_delta > 6) {
            return 1; /* VAMPIRE (carousel attack) */
        }
        if (rank > 950) {
            return 1; /* VAMPIRE (stretch attack) */
        }
    }
    
    /* Rule 2: Abnormal rank (stretch attack pattern) */
    if (rank > 1400) {
        return 1; /* VAMPIRE (stretch attack) */
    }
    
    /* Rule 3: Moderate DIO with high version delta */
    if (dio_rate > 20 && version_delta > 8) {
        return 1; /* VAMPIRE (carousel attack) */
    }
    
    /* Rule 4: Combined suspicious metrics */
    if (dio_rate > 25 && rank > 800 && version_delta > 4) {
        return 1; /* VAMPIRE */
    }
    
    return 0; /* NORMAL */
}

/**
 * Get confidence score for detection (optional)
 * Returns value 0-100 indicating confidence level
 */
static inline int vampire_detect_confidence(int16_t *features) {
    int16_t dio_rate = features[0];
    int16_t version_delta = features[1];
    int16_t rank = features[2];
    
    int score = 0;
    
    /* Accumulate suspicion score */
    if (dio_rate > 30) score += 30;
    else if (dio_rate > 20) score += 15;
    
    if (version_delta > 8) score += 30;
    else if (version_delta > 5) score += 15;
    
    if (rank > 1400) score += 40;
    else if (rank > 900) score += 20;
    
    return (score > 100) ? 100 : score;
}

#endif /* VAMPIRE_DETECTOR_H */
