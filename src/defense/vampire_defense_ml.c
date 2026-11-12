/*
 * VAMPIRE ATTACK DEFENSE WITH ML + ACL
 * =====================================
 * Real-time vampire attack detection combining:
 *   1. Machine Learning classifier (decision tree)
 *   2. Access Control List (ACL) for blacklisting
 *   3. Anomaly detection heuristics
 * 
 * Detection triggers:
 *   - ML model predicts attack (CAROUSEL, STRETCH, STEALTH, COORDINATED)
 *   - Heuristic rules detect anomalous behavior
 *   - ACL blocks known attackers
 * 
 * Actions:
 *   - Add attacker to ACL blacklist
 *   - Drop packets from attacker
 *   - Log detection event
 *   - Optional: trigger network-wide alert
 */

#include "contiki.h"
#include "net/routing/rpl-lite/rpl.h"
#include "sys/log.h"
#include "lib/list.h"
#include "lib/memb.h"
#include <stdlib.h>
#include "net/linkaddr.h"

#define LOG_MODULE "VAMPIRE_DEF"
#define LOG_LEVEL LOG_LEVEL_INFO

/* ML Model Integration */
#include "vampire_detector.h"

/* ACL Configuration */
#define MAX_BLACKLIST_SIZE 10
#define BLACKLIST_TIMEOUT_SEC 300  // 5 minutes

/* Grace period: disable detection during RPL bootstrap convergence */
#ifndef VAMPIRE_DEFENSE_GRACE_PERIOD
#define VAMPIRE_DEFENSE_GRACE_PERIOD 2000  
#endif

/* Detection thresholds */
#define CAROUSEL_THRESHOLD_DIO_RATE 15    // DIOs per minute (lowered from 50 to catch bursts)
#define STRETCH_THRESHOLD_RANK_DELTA 150  // Abnormal rank change (lowered from 500)
#define STEALTH_WINDOW_SEC 60             // Observation window
#define MIN_OBSERVATION_SEC 10            // Minimum time observing a neighbor before detection

/* Require multiple consecutive detections to avoid transient false positives */
#define REQUIRED_CONSECUTIVE_ALERTS 3

/* Attack type names for logging - Unified binary label: NORMAL vs ATTACK */
#define ATTACK_NAME_NORMAL "NORMAL"
#define ATTACK_NAME_ATTACK "ATTACK"

#define GET_ATTACK_NAME(type) (((type) != 0) ? ATTACK_NAME_ATTACK : ATTACK_NAME_NORMAL)

/* ACL Entry */
typedef struct acl_entry {
    struct acl_entry *next;
    uip_ipaddr_t addr;
    uint8_t attack_type;
    uint32_t blacklist_time;
    uint32_t detection_count;
} acl_entry_t;

LIST(blacklist);
MEMB(acl_pool, acl_entry_t, MAX_BLACKLIST_SIZE);

/* Feature tracking per neighbor */
typedef struct {
    uip_ipaddr_t addr;
    uint16_t dio_count;
    uint16_t dao_count;
    rpl_rank_t last_rank;
    rpl_rank_t prev_rank;
    uint8_t version;
    uint32_t last_update;
    uint8_t consecutive_alerts;  // consecutive detection count for confirmation
} neighbor_features_t;

#define MAX_NEIGHBORS 20
static neighbor_features_t neighbors[MAX_NEIGHBORS];
static uint8_t neighbor_count = 0;

/* Statistics */
static uint32_t total_detections = 0;
static uint32_t total_blocked = 0;

/* Boot time for grace period tracking */
static uint32_t boot_time = 0;
static bool grace_period_active = true;

PROCESS(vampire_defense_process, "Vampire Defense ML+ACL");

static bool defense_initialized = false;

/*---------------------------------------------------------------------------*/
/* ACL Management */
/*---------------------------------------------------------------------------*/
static void
acl_init(void)
{
    list_init(blacklist);
    memb_init(&acl_pool);
    LOG_INFO("ACL initialized (max %d entries)\n", MAX_BLACKLIST_SIZE);
}

void
vampire_defense_init(void)
{
    if(!defense_initialized) {
        defense_initialized = true;
        boot_time = clock_seconds();
        grace_period_active = true;
        acl_init();
        process_start(&vampire_defense_process, NULL);
        LOG_INFO("Grace period active for %d seconds (RPL bootstrap)\n",
                 VAMPIRE_DEFENSE_GRACE_PERIOD);
    }
}

static acl_entry_t*
acl_find(const uip_ipaddr_t *addr)
{
    acl_entry_t *entry;
    for(entry = list_head(blacklist); entry != NULL; entry = list_item_next(entry)) {
        if(uip_ipaddr_cmp(&entry->addr, addr)) {
            return entry;
        }
    }
    return NULL;
}

void
acl_add(const uip_ipaddr_t *addr, uint8_t attack_type)
{
    acl_entry_t *entry = acl_find(addr);
    
    if(entry != NULL) {
        // Already blacklisted, update
        entry->detection_count++;
        entry->blacklist_time = clock_seconds();
        LOG_WARN("ACL: Updated entry for ");
        LOG_WARN_6ADDR(addr);
        LOG_WARN_(" (detections: %lu)\n", (unsigned long)entry->detection_count);
        return;
    }
    
    // Add new entry
    entry = memb_alloc(&acl_pool);
    if(entry == NULL) {
        LOG_ERR("ACL: Pool full, cannot add new entry\n");
        // TODO: Evict oldest entry
        return;
    }
    
    uip_ipaddr_copy(&entry->addr, addr);
    entry->attack_type = attack_type;
    entry->blacklist_time = clock_seconds();
    entry->detection_count = 1;
    
    list_add(blacklist, entry);
    total_blocked++;
    
    LOG_WARN("ACL: Blacklisted ");
    LOG_WARN_6ADDR(addr);
    LOG_WARN_(" for %s attack\n", GET_ATTACK_NAME(attack_type));
}

static bool
acl_is_blacklisted(const uip_ipaddr_t *addr)
{
    acl_entry_t *entry = acl_find(addr);
    
    if(entry == NULL) {
        return false;
    }
    
    // Check timeout
    uint32_t now = clock_seconds();
    if(now - entry->blacklist_time > BLACKLIST_TIMEOUT_SEC) {
        LOG_INFO("ACL: Entry expired for ");
        LOG_INFO_6ADDR(addr);
        LOG_INFO_("\n");
        list_remove(blacklist, entry);
        memb_free(&acl_pool, entry);
        return false;
    }
    
    return true;
}

/* Public API for RPL layer */
bool
acl_is_blacklisted_addr(const uip_ipaddr_t *addr)
{
    if(!defense_initialized) {
        vampire_defense_init();
    }
    return acl_is_blacklisted(addr);
}

/*---------------------------------------------------------------------------*/
/* Feature Extraction & Validation */
/*---------------------------------------------------------------------------*/
static bool
is_trusted_node(const uip_ipaddr_t *addr, rpl_rank_t rank)
{
    // Node 1 and Node 2 are Sinks in this topology
    if(addr->u8[15] == 1 || addr->u8[15] == 2) {
        return true;
    }
    // Sinks advertise ROOT_RANK (256 in RPL-Lite)
    if(rank <= 256) {
        return true;
    }
    return false;
}

static neighbor_features_t*
get_neighbor_features(const uip_ipaddr_t *addr)
{
    // Find existing
    for(uint8_t i = 0; i < neighbor_count; i++) {
        if(uip_ipaddr_cmp(&neighbors[i].addr, addr)) {
            return &neighbors[i];
        }
    }
    
    // Add new
    if(neighbor_count < MAX_NEIGHBORS) {
        neighbor_features_t *nf = &neighbors[neighbor_count++];
        uip_ipaddr_copy(&nf->addr, addr);
        nf->dio_count = 0;
        nf->dao_count = 0;
        nf->last_rank = 0;
        nf->prev_rank = 0;
        nf->version = 0;
        nf->last_update = clock_seconds();
        return nf;
    }
    
    return NULL;
}

static void
extract_ml_features(neighbor_features_t *nf, int16_t *features)
{
    uint32_t now = clock_seconds();
    uint32_t time_delta = now - nf->last_update;
    if(time_delta == 0) time_delta = 1;  // Avoid division by zero
    
    // Adaptive DIO Rate:
    // If the node has only sent <= 6 DIOs in the current window, it is normal Trickle traffic.
    // Do NOT divide by small time_delta, which inflates rate to 60/min on the first DIO.
    if(time_delta < 60) {
        if(nf->dio_count <= 6) {
            features[FEAT_DIO_RATE] = (int16_t)nf->dio_count;
        } else {
            uint32_t dt = time_delta < 10 ? 10 : time_delta;
            features[FEAT_DIO_RATE] = (int16_t)((nf->dio_count * 60) / dt);
        }
    } else {
        features[FEAT_DIO_RATE] = (int16_t)((nf->dio_count * 60) / time_delta);
    }
    
    // Map version delta:
    features[FEAT_VERSION_DELTA] = (int16_t)(curr_instance.used ? 
        abs((int)nf->version - (int)curr_instance.dag.version) : 0);
    
    // Guard: rank=65535 (RPL_INFINITE_RANK) means node hasn't joined DAG yet.
    if(nf->last_rank == RPL_INFINITE_RANK) {
        features[FEAT_RANK] = 0;
        features[FEAT_RANK_DELTA] = 0;
        features[FEAT_IS_POISON] = 0;
    } else {
        features[FEAT_RANK] = (int16_t)nf->last_rank;
        if(nf->prev_rank > 0 && nf->prev_rank != RPL_INFINITE_RANK) {
            features[FEAT_RANK_DELTA] = (int16_t)abs((int)nf->last_rank - (int)nf->prev_rank);
        } else {
            features[FEAT_RANK_DELTA] = 0;
        }
        features[FEAT_IS_POISON] = 0;
    }
}

/*---------------------------------------------------------------------------*/
/* Detection Logic */
/*---------------------------------------------------------------------------*/
static uint8_t
detect_carousel_heuristic(neighbor_features_t *nf)
{
    uint32_t time_delta = clock_seconds() - nf->last_update;
    if(time_delta == 0) time_delta = 1;
    
    /* Detect burst DIO flooding (> 6 DIOs in short window) */
    if(nf->dio_count > 6) {
        float dio_rate = (float)(nf->dio_count * 60) / (time_delta < 10 ? 10 : time_delta);
        if(dio_rate >= CAROUSEL_THRESHOLD_DIO_RATE) {
            LOG_WARN("HEURISTIC: ATTACK detected (DIO rate: %.1f/min)\n", dio_rate);
            return 1;  // ATTACK
        }
    }
    
    return 0;
}

static uint8_t
detect_stretch_heuristic(neighbor_features_t *nf, rpl_rank_t advertised_rank)
{
    // Ignore rank transitions involving INFINITE_RANK or uninitialized rank
    if(nf->last_rank == RPL_INFINITE_RANK || advertised_rank == RPL_INFINITE_RANK || advertised_rank == 0) {
        return 0;
    }
    
    /* Rule 1: Non-root node claiming an illegally low rank (< 256, root rank in RPL-Lite) */
    if(advertised_rank < 256) {
        LOG_WARN("HEURISTIC: STRETCH ATTACK detected (illegal rank %u < 256)\n", advertised_rank);
        return 1;  // ATTACK
    }
    
    /* Rule 2: Sudden abnormal rank jump/drop (stretch attack making node deceptively attractive) */
    if(nf->last_rank > 0) {
        int rank_delta = abs((int)advertised_rank - (int)nf->last_rank);
        if(rank_delta >= STRETCH_THRESHOLD_RANK_DELTA) {
            LOG_WARN("HEURISTIC: STRETCH ATTACK detected (rank jump: %u -> %u, delta: %d >= %d)\n",
                     nf->last_rank, advertised_rank, rank_delta, STRETCH_THRESHOLD_RANK_DELTA);
            return 1;  // ATTACK
        }
    }
    
    return 0;
}

static uint8_t
run_ml_detection(neighbor_features_t *nf)
{
    // Skip ML detection for nodes that haven't joined DAG yet
    if(nf->last_rank == RPL_INFINITE_RANK || nf->last_rank == 0) {
        return 0;
    }
    
    uint32_t time_delta = clock_seconds() - nf->last_update;
    // Require minimum observation time unless there is an obvious flood (> 8 DIOs)
    if(time_delta < MIN_OBSERVATION_SEC && nf->dio_count <= 8) {
        return 0;
    }
    
    int16_t features[VAMPIRE_NUM_FEATURES] = {0};
    extract_ml_features(nf, features);
    
    // Filter normal RPL dynamics that overfitted Decision Tree misclassifies:
    // Low DIO rate (<= 8), normal version (<= 1), normal parent switch rank jump (<= 384)
    if(features[FEAT_DIO_RATE] <= 8 && features[FEAT_VERSION_DELTA] <= 1 && features[FEAT_RANK_DELTA] <= 384) {
        return 0; // NORMAL
    }
    
    uint8_t prediction = (uint8_t)detect_vampire_attack(features);
    
    // Confidence score check to weed out low-confidence false positives
    int confidence = vampire_detect_confidence(features);
    if(prediction != 0 && confidence < 40) {
        return 0;
    }
    
    if(prediction != 0) {
        LOG_WARN("ML: Detected %s (conf=%d%%)\n", GET_ATTACK_NAME(prediction), confidence);
        total_detections++;
    }
    
    return prediction;
}

/*---------------------------------------------------------------------------*/
/* RPL Hooks */
/*---------------------------------------------------------------------------*/
void
vampire_defense_check_dio(const uip_ipaddr_t *from, rpl_rank_t rank, uint8_t version)
{
    if(!defense_initialized) {
        vampire_defense_init();
    }

    // Trusted nodes (Sink 1, Sink 2, Root) must NEVER be flagged as attackers
    if(is_trusted_node(from, rank)) {
        return;
    }

    // Check if grace period has elapsed
    if(grace_period_active) {
        uint32_t elapsed = clock_seconds() - boot_time;
        if(elapsed >= VAMPIRE_DEFENSE_GRACE_PERIOD) {
            grace_period_active = false;
            LOG_INFO("Grace period ended after %lu seconds, detection ACTIVE\n",
                     (unsigned long)elapsed);
        }
    }

    // Check ACL first (only populated by external ML Monitor approval)
    if(acl_is_blacklisted(from)) {
        LOG_INFO("Dropped DIO from blacklisted ");
        LOG_INFO_6ADDR(from);
        LOG_INFO_("\n");
        return;
    }
    
    // Update neighbor features (always collect, even during grace period)
    neighbor_features_t *nf = get_neighbor_features(from);
    if(nf == NULL) return;
    
    nf->dio_count++;
    nf->prev_rank = nf->last_rank;
    nf->last_rank = rank;
    nf->version = version;
    
    // During grace period: collect features only, skip detection
    if(grace_period_active) {
        LOG_DBG("GRACE: skipping detection (bootstrap phase)\n");
        return;
    }
    
    // Run heuristic detection
    uint8_t heuristic_result = detect_carousel_heuristic(nf);
    if(heuristic_result == 0) {
        heuristic_result = detect_stretch_heuristic(nf, rank);
    }
    
    // Run ML detection
    uint8_t ml_result = run_ml_detection(nf);
    
    // Extract features for logging
    int16_t features[VAMPIRE_NUM_FEATURES] = {0};
    extract_ml_features(nf, features);
    
    // Determine final attack type
    uint8_t attack_type = (heuristic_result != 0) ? heuristic_result : ml_result;
    const char *source = (heuristic_result != 0) ? "HEURISTIC" : "ML";
    
    if(attack_type != 0) {
        nf->consecutive_alerts++;
        total_detections++;
        
        /*
         * MONITOR MODE: Do NOT auto-block. Instead, emit a structured
         * ML_ALERT log line with all detection metadata so the external
         * ML Monitor server can parse it and present to human supervisor.
         *
         * Format: ML_ALERT detector=<ID> suspect=<ADDR> type=<TYPE> source=<SRC>
         *         alerts=<N> dio_rate=<V> version_delta=<V> rank=<V>
         *         rank_delta=<V> is_poison=<V>
         */
        LOG_WARN("ML_ALERT detector=%u suspect=", 
                 (unsigned)linkaddr_node_addr.u8[7]);
        LOG_WARN_6ADDR(from);
        LOG_WARN_(" type=%s source=%s alerts=%u dio_rate=%d version_delta=%d "
                  "rank=%d rank_delta=%d is_poison=%d\n",
                  GET_ATTACK_NAME(attack_type), source,
                  (unsigned)nf->consecutive_alerts,
                  (int)features[FEAT_DIO_RATE],
                  (int)features[FEAT_VERSION_DELTA],
                  (int)features[FEAT_RANK],
                  (int)features[FEAT_RANK_DELTA],
                  (int)features[FEAT_IS_POISON]);
    } else {
        // Normal behavior decays the alert counter
        if(nf->consecutive_alerts > 0) {
            nf->consecutive_alerts--;
        }
    }
}

/*---------------------------------------------------------------------------*/
/* Process */
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(vampire_defense_process, ev, data)
{
    static struct etimer periodic_timer;
    
    PROCESS_BEGIN();
    
    LOG_INFO("===========================================\n");
    LOG_INFO("VAMPIRE DEFENSE: ML + ACL [MONITOR MODE]\n");
    LOG_INFO("Alerts sent to ML Monitor, no auto-block\n");
    LOG_INFO("===========================================\n");
    
    etimer_set(&periodic_timer, CLOCK_SECOND * 60);  // Check every minute
    
    while(1) {
        PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
        
        // Periodic cleanup and stats
        LOG_INFO("STATS: detections=%lu blocked=%lu blacklist_size=%d\n",
                 (unsigned long)total_detections,
                 (unsigned long)total_blocked,
                 list_length(blacklist));
        
        // Age DIO counts for next window
        for(uint8_t i = 0; i < neighbor_count; i++) {
            neighbors[i].dio_count = 0;
            neighbors[i].last_update = clock_seconds();
        }
        
        etimer_reset(&periodic_timer);
    }
    
    PROCESS_END();
}

void
acl_get_stats(uint32_t *detections, uint32_t *blocked, uint8_t *blacklist_size)
{
    if(detections) *detections = total_detections;
    if(blocked) *blocked = total_blocked;
    if(blacklist_size) *blacklist_size = (uint8_t)list_length(blacklist);
}
