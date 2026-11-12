#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --- Routing: Khoa cung MRHOF, khong phu thuoc default ngam --- */
#define RPL_CONF_OF_OCP RPL_OCP_MRHOF

/* --- MAC: TSCH tu dong khoi dong --- */
#define TSCH_CONF_AUTOSTART 1
#define TSCH_CONF_EB_PERIOD (4 * CLOCK_SECOND)
#define NBR_TABLE_CONF_MAX_NEIGHBORS 35
#define UIP_CONF_MAX_ROUTES 40

/* Limit neighbor queue depth and MAC retries to prevent buffer starvation */
#define TSCH_QUEUE_CONF_NUM_PER_NEIGHBOR 32
#define TSCH_CONF_MAC_MAX_FRAME_RETRIES 7

/* --- 802.15.4 FRAME VERSION (required for TSCH) --- */
#define FRAME802154_CONF_VERSION FRAME802154_IEEE802154_2015

#define ENERGEST_CONF_ON 1

#define LOG_CONF_LEVEL_RPL LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_MAC LOG_LEVEL_WARN   /* Doi thanh LOG_LEVEL_DBG khi can kiem tra chi tiet tang MAC */
#define LOG_CONF_LEVEL_APP LOG_LEVEL_INFO

/* Enable logs from NODE and SINK modules */
#define LOG_CONF_LEVEL_DEFAULT LOG_LEVEL_INFO

/* --- Vampire Attack Defense (ML + ACL Blacklist) --- */
/* Uncomment the line below to activate defense on all nodes */
#define VAMPIRE_DEFENSE_ENABLED 1

/* Grace period (seconds) to let RPL converge before enabling detection.
 * During this period, features are collected but no blacklisting occurs.
 * Default: 180s. Increase for larger networks or slower convergence. */
#define VAMPIRE_DEFENSE_GRACE_PERIOD 180

#endif

