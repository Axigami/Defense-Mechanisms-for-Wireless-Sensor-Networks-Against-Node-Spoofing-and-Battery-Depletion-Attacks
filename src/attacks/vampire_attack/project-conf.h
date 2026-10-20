#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --- Routing: khóa cứng MRHOF, không phụ thuộc default ngầm --- */
#define RPL_CONF_OF_OCP RPL_OCP_MRHOF

/* --- MAC: TSCH tự khởi động --- */
#define TSCH_CONF_AUTOSTART 1
#define TSCH_CONF_EB_PERIOD (4 * CLOCK_SECOND)
#define NBR_TABLE_CONF_MAX_NEIGHBORS 20
#define UIP_CONF_MAX_ROUTES 30

/* Limit neighbor queue depth and MAC retries to prevent buffer starvation */
#define TSCH_QUEUE_CONF_NUM_PER_NEIGHBOR 8
#define TSCH_CONF_MAC_MAX_FRAME_RETRIES 3

/* --- 802.15.4 FRAME VERSION (required for TSCH) --- */
#define FRAME802154_CONF_VERSION FRAME802154_IEEE802154_2015

#define ENERGEST_CONF_ON 1

#define LOG_CONF_LEVEL_RPL LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_MAC LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_APP LOG_LEVEL_INFO

/* Enable logs from NODE and SINK modules */
#define LOG_CONF_LEVEL_DEFAULT LOG_LEVEL_INFO

#endif /* PROJECT_CONF_H_ */
