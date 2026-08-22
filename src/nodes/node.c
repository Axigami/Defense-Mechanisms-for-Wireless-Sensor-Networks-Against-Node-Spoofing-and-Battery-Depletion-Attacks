#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/energest.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"

#define LOG_MODULE "NODE"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765
#define SEND_INTERVAL     (60 * CLOCK_SECOND)
#define STATUS_INTERVAL   (5 * 60 * CLOCK_SECOND)

#define INITIAL_ENERGY_MJ 7200

#define VOLTAGE_V        3.0
#define CURRENT_TX_MA    17.4
#define CURRENT_RX_MA    20.0
#define CURRENT_CPU_MA    1.8
#define CURRENT_LPM_MA    0.0545

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

static uint32_t residual_mj = INITIAL_ENERGY_MJ;
static uint32_t last_cpu, last_lpm, last_tx, last_rx;
static uint32_t sim_start_time;
static uint8_t node_is_dead = 0;

static double
energy_tick_and_get_duty(void)
{
  if(node_is_dead) {
    return 0.0;
  }

  uint32_t cpu = energest_type_time(ENERGEST_TYPE_CPU) - last_cpu;
  uint32_t lpm = energest_type_time(ENERGEST_TYPE_LPM) - last_lpm;
  uint32_t tx  = energest_type_time(ENERGEST_TYPE_TRANSMIT) - last_tx;
  uint32_t rx  = energest_type_time(ENERGEST_TYPE_LISTEN) - last_rx;
  last_cpu += cpu; last_lpm += lpm; last_tx += tx; last_rx += rx;

  double t_cpu = (double)cpu / ENERGEST_SECOND;
  double t_lpm = (double)lpm / ENERGEST_SECOND;
  double t_tx  = (double)tx  / ENERGEST_SECOND;
  double t_rx  = (double)rx  / ENERGEST_SECOND;

  double consumed_mj = VOLTAGE_V * (CURRENT_CPU_MA * t_cpu + CURRENT_LPM_MA * t_lpm
                                    + CURRENT_TX_MA  * t_tx  + CURRENT_RX_MA  * t_rx);
  
  if(consumed_mj >= (double)residual_mj) {
    residual_mj = 0;
  } else {
    residual_mj -= (uint32_t)consumed_mj;
  }

  double elapsed_radio_on_s = t_tx + t_rx;
  double elapsed_total_s = t_cpu + t_lpm;
  return elapsed_total_s > 0 ? (elapsed_radio_on_s / elapsed_total_s) * 100.0 : 0.0;
}

PROCESS(node_process, "Sensor node");
PROCESS(status_process, "Status reporter");
AUTOSTART_PROCESSES(&node_process, &status_process);

PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer et;
  static uip_ipaddr_t dest_ipaddr;
  static uint16_t cluster_id;
  static uint32_t gen_count = 0, sent_count = 0;

  PROCESS_BEGIN();
  sim_start_time = clock_time();
  cluster_id = (node_id <= 26) ? 1 : 2;

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  etimer_set(&et, random_rand() % SEND_INTERVAL);
  PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&et));

  while(1) {
    etimer_set(&et, SEND_INTERVAL);
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&et));

    energy_tick_and_get_duty();
    
    if(residual_mj == 0 && !node_is_dead) {
      node_is_dead = 1;
      uint32_t alive_s = (clock_time() - sim_start_time) / CLOCK_SECOND;
      
      LOG_INFO("DEAD cluster=%u node=%u time_alive_s=%lu last_seq=%lu total_gen=%lu total_sent=%lu\n",
               cluster_id, node_id, (unsigned long)alive_s,
               (unsigned long)(sent_count > 0 ? sent_count - 1 : 0), 
               (unsigned long)gen_count, (unsigned long)sent_count);
      
      PROCESS_EXIT();
    }
    
    if(node_is_dead) {
      PROCESS_EXIT();
    }

    gen_count++;
    LOG_INFO("GEN cluster=%u node=%u gen_count=%lu\n", cluster_id, node_id, (unsigned long)gen_count);

    if(NETSTACK_ROUTING.node_is_reachable() &&
       NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {
      sensor_payload_t p = {
        .cluster_id = cluster_id, .node_id_f = node_id,
        .seqno = sent_count++, .residual_mj = residual_mj, .tx_time = clock_time()
      };
      simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);
      LOG_INFO("TX cluster=%u node=%u seq=%lu energy_mj=%lu bytes=%u\n",
               cluster_id, node_id, (unsigned long)p.seqno,
               (unsigned long)residual_mj, (unsigned int)sizeof(p));
    } else {
      LOG_INFO("TXFAIL cluster=%u node=%u gen_count=%lu\n", cluster_id, node_id, (unsigned long)gen_count);
    }
  }
  PROCESS_END();
}

PROCESS_THREAD(status_process, ev, data)
{
  static struct etimer et;
  PROCESS_BEGIN();
  
  while(1) {
    etimer_set(&et, STATUS_INTERVAL);
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&et));

    if(node_is_dead) {
      LOG_INFO("STATUS node=%u STOPPED\n", node_id);
      PROCESS_EXIT();
    }

    double duty = energy_tick_and_get_duty();
    uint16_t rank = curr_instance.dag.rank;
    LOG_INFO("STATUS node=%u energy_mj=%lu duty_pct=%d rank=%u\n",
             node_id, (unsigned long)residual_mj, (int)duty, rank);
  }
  PROCESS_END();
}
