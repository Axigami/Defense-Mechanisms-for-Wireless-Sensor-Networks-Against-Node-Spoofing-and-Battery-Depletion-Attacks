CONTIKI_PROJECT = node sink sybil_node vampire_node
all: $(CONTIKI_PROJECT)

MAKE_MAC     = MAKE_MAC_TSCH
MAKE_ROUTING = MAKE_ROUTING_RPL_LITE
MODULES     += os/services/orchestra

# Vampire Defense Integration
CFLAGS += -I../defense
PROJECTDIRS += ../defense
PROJECT_SOURCEFILES += vampire_defense_ml.c

CONTIKI = ../contiki-ng

include $(CONTIKI)/Makefile.include
