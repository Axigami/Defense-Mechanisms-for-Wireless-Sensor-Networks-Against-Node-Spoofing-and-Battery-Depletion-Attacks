#include "contiki.h"
#include "net/routing/routing.h"
#include "net/ipv6/uip-ds6-route.h"
#include "simple-udp.h"
#include "sys/node-id.h"
#include "sys/log.h"

#define LOG_MODULE "SINK"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765
#define HEALTH_INTERVAL (5 * 60 * CLOCK_SECOND)

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

static void
rx_callback(struct simple_udp_connection *c,
            const uip_ipaddr_t *sender_addr, uint16_t sender_port,
            const uip_ipaddr_t *receiver_addr, uint16_t receiver_port,
            const uint8_t *data, uint16_t datalen)
{
  const sensor_payload_t *p = (const sensor_payload_t *)data;
  uint32_t latency_ms = (uint32_t)((clock_time() - p->tx_time) * 1000UL / CLOCK_SECOND);

  /* Dòng RX là nguồn cho #6, #8, #9, #10, #12 và cả 4 mục phân tích tổng hợp */
  LOG_INFO("RX sink=%u cluster=%u node=%u seq=%lu energy_mj=%lu bytes=%u latency_ms=%lu\n",
           node_id, p->cluster_id, p->node_id_f,
           (unsigned long)p->seqno, (unsigned long)p->residual_mj,
           datalen, (unsigned long)latency_ms);
}

PROCESS(sink_process, "Sink node");
PROCESS(health_process, "Network health monitor");
AUTOSTART_PROCESSES(&sink_process, &health_process);

PROCESS_THREAD(sink_process, ev, data)
{
  PROCESS_BEGIN();
  NETSTACK_ROUTING.root_start();
  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, rx_callback);
  PROCESS_END();
}

PROCESS_THREAD(health_process, ev, data)
{
  static struct etimer et;
  PROCESS_BEGIN();
  while(1) {
    etimer_set(&et, HEALTH_INTERVAL);
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&et));
    LOG_INFO("HEALTH sink=%u active_routes=%u\n", node_id, uip_ds6_route_num_routes());
  }
  PROCESS_END();
}
