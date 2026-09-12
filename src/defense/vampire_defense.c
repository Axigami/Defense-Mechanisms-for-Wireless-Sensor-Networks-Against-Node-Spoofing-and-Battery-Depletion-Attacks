/**
 * Vampire Attack Defense System - Implementation
 */

#include "vampire_defense.h"
#include "vampire_detector.h"  /* Auto-generated decision tree */
#include "sys/log.h"
#include <string.h>

#define LOG_MODULE "VAMP-DEF"
#define LOG_LEVEL LOG_LEVEL_INFO

/* Global variables */
acl_entry_t vampire_acl[MAX_ACL_ENTRIES];
int vampire_acl_count = 0;

/* Neighbor monitoring table */
#define MAX_MONITORED_NEIGHBORS 20
static neighbor_features_t neighbors[MAX_MONITORED_NEIGHBORS];
static int neighbor_count = 0;

/* RPL version from root (for version_delta calculation) */
static uint16_t root_version = 0;

/*---------------------------------------------------------------------------*/
void
vampire_defense_init(void)
{
  /* Clear ACL table */
  memset(vampire_acl, 0, sizeof(vampire_acl));
  vampire_acl_count = 0;
  
  /* Clear neighbor table */
  memset(neighbors, 0, sizeof(neighbors));
  neighbor_count = 0;
  
  /* Get root version nếu available */
  if(curr_instance.used && curr_instance.dag.rank != RPL_INFINITE_RANK) {
    root_version = curr_instance.dag.version;
  }
  
  LOG_INFO("Vampire defense initialized\n");
}

/*---------------------------------------------------------------------------*/
void
vampire_defense_update_dio(const uip_ipaddr_t *from)
{
  int i;
  uint32_t now = clock_seconds();
  
  /* Tìm neighbor trong table */
  for(i = 0; i < neighbor_count; i++) {
    if(uip_ipaddr_cmp(&neighbors[i].addr, from)) {
      /* Update DIO count */
      neighbors[i].dio_count++;
      neighbors[i].last_dio_time = now;
      return;
    }
  }
  
  /* Neighbor mới - thêm vào table */
  if(neighbor_count < MAX_MONITORED_NEIGHBORS) {
    uip_ipaddr_copy(&neighbors[neighbor_count].addr, from);
    neighbors[neighbor_count].dio_count = 1;
    neighbors[neighbor_count].last_dio_time = now;
    neighbors[neighbor_count].monitored = 1;
    neighbor_count++;
  }
}

/*---------------------------------------------------------------------------*/
int
vampire_defense_check_neighbors(void)
{
  int i, detected = 0;
  uint32_t now = clock_seconds();
  int16_t features[3];
  
  /* Update root version */
  if(curr_instance.used && curr_instance.dag.rank != RPL_INFINITE_RANK) {
    root_version = curr_instance.dag.version;
  }
  
  /* Check mỗi neighbor */
  for(i = 0; i < neighbor_count; i++) {
    if(!neighbors[i].monitored) continue;
    
    /* Skip nếu timeout (>120s không có DIO) */
    if(now - neighbors[i].last_dio_time > 120) {
      neighbors[i].dio_count = 0;
      neighbors[i].monitored = 0;
      continue;
    }
    
    /* Extract features từ RPL neighbor info */
    rpl_nbr_t *nbr = rpl_neighbor_get_from_ipaddr(&neighbors[i].addr);
    if(nbr != NULL) {
      /* Feature 0: DIO rate (normalized to 60s window) */
      features[0] = neighbors[i].dio_count;
      
      /* Feature 1: Version delta */
      uint16_t nbr_version = 0;  /* Get từ DIO message */
      features[1] = (int16_t)(nbr_version > root_version ? 
                              nbr_version - root_version : 
                              root_version - nbr_version);
      
      /* Feature 2: Rank */
      features[2] = (int16_t)nbr->rank;
      
      /* Run decision tree detector */
      int result = vampire_detect(features);
      
      if(result == 1) {
        /* VAMPIRE ATTACK DETECTED! */
        LOG_WARN("Vampire attack detected from ");
        LOG_WARN_6ADDR(&neighbors[i].addr);
        LOG_WARN_(" (DIO=%d, VDelta=%d, Rank=%d)\n", 
                  features[0], features[1], features[2]);
        
        /* Add to ACL */
        if(vampire_defense_add_to_acl(&neighbors[i].addr)) {
          detected++;
        }
      }
    }
    
    /* Reset DIO count cho next window */
    neighbors[i].dio_count = 0;
  }
  
  return detected;
}

/*---------------------------------------------------------------------------*/
int
vampire_defense_is_blocked(const uip_ipaddr_t *addr)
{
  int i;
  
  for(i = 0; i < vampire_acl_count; i++) {
    if(vampire_acl[i].active && 
       uip_ipaddr_cmp(&vampire_acl[i].addr, addr)) {
      return 1;  /* BLOCKED */
    }
  }
  
  return 0;  /* ALLOWED */
}

/*---------------------------------------------------------------------------*/
int
vampire_defense_add_to_acl(const uip_ipaddr_t *addr)
{
  int i;
  
  /* Check if already in ACL */
  for(i = 0; i < vampire_acl_count; i++) {
    if(vampire_acl[i].active && 
       uip_ipaddr_cmp(&vampire_acl[i].addr, addr)) {
      return 1;  /* Already blocked */
    }
  }
  
  /* Add new entry */
  if(vampire_acl_count < MAX_ACL_ENTRIES) {
    uip_ipaddr_copy(&vampire_acl[vampire_acl_count].addr, addr);
    vampire_acl[vampire_acl_count].blocked_time = clock_seconds();
    vampire_acl[vampire_acl_count].active = 1;
    vampire_acl_count++;
    
    LOG_INFO("Added to ACL blacklist: ");
    LOG_INFO_6ADDR(addr);
    LOG_INFO_("\n");
    
    return 1;
  }
  
  LOG_WARN("ACL table full! Cannot add ");
  LOG_WARN_6ADDR(addr);
  LOG_WARN_("\n");
  
  return 0;
}

/*---------------------------------------------------------------------------*/
void
vampire_defense_remove_from_acl(const uip_ipaddr_t *addr)
{
  int i, j;
  
  for(i = 0; i < vampire_acl_count; i++) {
    if(vampire_acl[i].active && 
       uip_ipaddr_cmp(&vampire_acl[i].addr, addr)) {
      /* Shift remaining entries */
      for(j = i; j < vampire_acl_count - 1; j++) {
        vampire_acl[j] = vampire_acl[j + 1];
      }
      vampire_acl_count--;
      
      LOG_INFO("Removed from ACL: ");
      LOG_INFO_6ADDR(addr);
      LOG_INFO_("\n");
      return;
    }
  }
}

/*---------------------------------------------------------------------------*/
void
vampire_defense_clear_acl(void)
{
  memset(vampire_acl, 0, sizeof(vampire_acl));
  vampire_acl_count = 0;
  LOG_INFO("ACL cleared\n");
}

/*---------------------------------------------------------------------------*/
void
vampire_defense_print_acl(void)
{
  int i;
  
  LOG_INFO("ACL Blacklist (%d entries):\n", vampire_acl_count);
  for(i = 0; i < vampire_acl_count; i++) {
    if(vampire_acl[i].active) {
      LOG_INFO("  [%d] ", i);
      LOG_INFO_6ADDR(&vampire_acl[i].addr);
      LOG_INFO_(" (blocked at %lu)\n", 
                (unsigned long)vampire_acl[i].blocked_time);
    }
  }
}
