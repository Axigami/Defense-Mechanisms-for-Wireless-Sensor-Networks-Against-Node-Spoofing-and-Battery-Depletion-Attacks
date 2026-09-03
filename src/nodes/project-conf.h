#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --- Routing: khóa cứng MRHOF, không phụ thuộc default ngầm --- */
#define RPL_CONF_OF_OCP RPL_OCP_MRHOF

/* --- MAC: TSCH tự khởi động --- */
#define TSCH_CONF_AUTOSTART 1
#define TSCH_CONF_EB_PERIOD (4 * CLOCK_SECOND)
#define NBR_TABLE_CONF_MAX_NEIGHBORS 20
#define UIP_CONF_MAX_ROUTES 30

#define ENERGEST_CONF_ON 1

#define LOG_CONF_LEVEL_RPL LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_MAC LOG_LEVEL_WARN   /* đổi thành LOG_LEVEL_DBG khi cần soi #15 */
#define LOG_CONF_LEVEL_APP LOG_LEVEL_INFO

/* Enable logs from NODE and SINK modules */
#define LOG_CONF_LEVEL_DEFAULT LOG_LEVEL_INFO

#endif
