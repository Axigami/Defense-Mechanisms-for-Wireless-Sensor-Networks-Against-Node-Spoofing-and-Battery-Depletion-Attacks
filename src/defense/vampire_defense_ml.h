/*
 * VAMPIRE DEFENSE ML+ACL - Header
 */

#ifndef VAMPIRE_DEFENSE_ML_H
#define VAMPIRE_DEFENSE_ML_H

#include "net/ipv6/uip.h"
#include <stdbool.h>

/* Grace period: detection is disabled for this many seconds after boot
 * to allow RPL topology convergence without false positives.
 * Override in project-conf.h with VAMPIRE_DEFENSE_GRACE_PERIOD. */
#ifndef VAMPIRE_DEFENSE_GRACE_PERIOD
#define VAMPIRE_DEFENSE_GRACE_PERIOD 2000
#endif

/* Public API */

/**
 * Add an IPv6 address to the ACL blacklist
 * @param addr IPv6 address to blacklist
 * @param attack_type Attack type identifier
 */
void acl_add(const uip_ipaddr_t *addr, uint8_t attack_type);

/**
 * Check if an IPv6 address is blacklisted
 * @param addr IPv6 address to check
 * @return true if blacklisted, false otherwise
 */
bool acl_is_blacklisted_addr(const uip_ipaddr_t *addr);

/**
 * Check DIO packet for vampire attack patterns.
 * During grace period (first VAMPIRE_DEFENSE_GRACE_PERIOD seconds),
 * features are collected but detection is suppressed.
 * After grace period, requires REQUIRED_CONSECUTIVE_ALERTS (2)
 * consecutive detections before blacklisting.
 * 
 * Called by RPL layer after receiving DIO.
 * @param from Source IPv6 address
 * @param rank Advertised rank
 * @param version DAG version
 */
void vampire_defense_check_dio(const uip_ipaddr_t *from, 
                               uint16_t rank, uint8_t version);

/**
 * Initialize vampire defense module and start periodic background process.
 * Records boot_time for grace period calculation.
 */
void vampire_defense_init(void);

/**
 * Get ACL statistics
 */
void acl_get_stats(uint32_t *detections, uint32_t *blocked, uint8_t *blacklist_size);

#endif /* VAMPIRE_DEFENSE_ML_H */

