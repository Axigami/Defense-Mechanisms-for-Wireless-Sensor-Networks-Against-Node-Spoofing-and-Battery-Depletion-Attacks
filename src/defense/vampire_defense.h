/**
 * Vampire Attack Defense System
 * 
 * Feature extraction và ACL enforcement cho Contiki-NG
 * Implement tại tầng mạng trên các node trung gian
 */

#ifndef VAMPIRE_DEFENSE_H
#define VAMPIRE_DEFENSE_H

#include "contiki.h"
#include "net/routing/rpl-lite/rpl.h"
#include "net/ipv6/uip.h"
#include "sys/ctimer.h"

/* Configuration */
#define VAMPIRE_CHECK_INTERVAL (60 * CLOCK_SECOND)  /* Check mỗi 60s */
#define MAX_ACL_ENTRIES 10                           /* Max số attacker trong ACL */
#define DIO_WINDOW_SIZE 60                          /* DIO counting window (seconds) */

/* Feature thresholds (dựa trên training) */
#define NORMAL_DIO_RATE_MAX 25
#define NORMAL_VERSION_DELTA_MAX 5
#define NORMAL_RANK_MAX 1200

/* ACL entry structure */
typedef struct acl_entry {
  uip_ipaddr_t addr;
  uint32_t blocked_time;
  uint8_t active;
} acl_entry_t;

/* Feature vector cho mỗi neighbor */
typedef struct neighbor_features {
  uip_ipaddr_t addr;
  uint16_t dio_count;          /* Số DIO trong window */
  uint16_t version_delta;      /* Chênh lệch version */
  uint16_t rank;               /* RPL rank */
  uint32_t last_dio_time;      /* Timestamp của DIO cuối */
  uint8_t monitored;           /* Đang theo dõi */
} neighbor_features_t;

/* Global ACL table */
extern acl_entry_t vampire_acl[MAX_ACL_ENTRIES];
extern int vampire_acl_count;

/**
 * Initialize vampire defense system
 */
void vampire_defense_init(void);

/**
 * Update DIO count cho neighbor khi nhận DIO message
 * Gọi từ RPL DIO callback
 */
void vampire_defense_update_dio(const uip_ipaddr_t *from);

/**
 * Extract features và check for vampire attack
 * Gọi định kỳ từ process
 * 
 * @return Số attackers detected
 */
int vampire_defense_check_neighbors(void);

/**
 * Check if address is in ACL blacklist
 * Gọi trước khi forward packet
 * 
 * @param addr IPv6 address to check
 * @return 1 if blocked, 0 if allowed
 */
int vampire_defense_is_blocked(const uip_ipaddr_t *addr);

/**
 * Add address to ACL blacklist
 * 
 * @param addr IPv6 address to block
 * @return 1 if added successfully, 0 if ACL full
 */
int vampire_defense_add_to_acl(const uip_ipaddr_t *addr);

/**
 * Remove address from ACL (for testing)
 */
void vampire_defense_remove_from_acl(const uip_ipaddr_t *addr);

/**
 * Clear all ACL entries
 */
void vampire_defense_clear_acl(void);

/**
 * Get ACL statistics
 */
void vampire_defense_print_acl(void);

#endif /* VAMPIRE_DEFENSE_H */
