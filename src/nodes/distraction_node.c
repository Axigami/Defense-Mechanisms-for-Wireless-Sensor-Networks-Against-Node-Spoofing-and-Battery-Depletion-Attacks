#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/energest.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"
#include "dev/serial-line.h"
#include <stdbool.h>
#include <string.h>

#define LOG_MODULE "ATTACK"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765
#define SEND_INTERVAL     (60 * CLOCK_SECOND)

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;
static uint32_t gen_count = 0;
static bool is_attacking = false;

PROCESS(attack_process, "Attack Process");
AUTOSTART_PROCESSES(&attack_process);

PROCESS_THREAD(attack_process, ev, data)
{
  static struct etimer et;
  static uip_ipaddr_t dest_ipaddr;

  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  etimer_set(&et, random_rand() % SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT();

    if(ev == serial_line_event_message && data != NULL) {
      char *str = (char *)data;
      if(strncmp(str, "START_DISTRACTION", 17) == 0) {
        LOG_INFO("Received START_DISTRACTION command via serial. Initiating attack...\n");
        is_attacking = true;
        // Reset timer to attack faster
        etimer_set(&et, CLOCK_SECOND);
      } else if(strncmp(str, "STOP_DISTRACTION", 16) == 0) {
        LOG_INFO("Received STOP_DISTRACTION command via serial. Stopping attack.\n");
        is_attacking = false;
        etimer_set(&et, SEND_INTERVAL);
      }
    }

    if(ev == PROCESS_EVENT_TIMER && etimer_expired(&et)) {
      if(NETSTACK_ROUTING.node_is_reachable() && NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {
        sensor_payload_t p;
        p.cluster_id = 1;
        p.seqno = gen_count++;
        p.residual_mj = 15000;
        p.tx_time = clock_time();
        
        
        if(is_attacking) {
            p.node_id_f = 200 + (random_rand() % 50); // Fake IDs 200+
            p.temperature_c = 250; // Fake normal temp to hide fire
        } else {
            p.node_id_f = node_id; // Normal behavior
            p.temperature_c = (int16_t)(250 + (random_rand() % 50));
        }
        LOG_INFO("DISTRACT_NODE sending ID=%u temp=%d\n", p.node_id_f, p.temperature_c);


        simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);
      }
      
      if(is_attacking) {
        etimer_set(&et, 3 * CLOCK_SECOND); // Attack very fast
      } else {
        etimer_set(&et, SEND_INTERVAL);
      }
    }
  }

  PROCESS_END();
}
