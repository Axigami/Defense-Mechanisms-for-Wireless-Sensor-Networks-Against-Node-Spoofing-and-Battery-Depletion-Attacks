CONTIKI_PROJECT = node sink sybil_node vampire_node hijacked_node distraction_node burning_node
all: $(CONTIKI_PROJECT)

MAKE_MAC     = MAKE_MAC_TSCH
MAKE_ROUTING = MAKE_ROUTING_RPL_LITE
MODULES     += os/services/orchestra

# Vampire Defense Integration
CFLAGS += -I../defense
PROJECTDIRS += ../defense
PROJECT_SOURCEFILES += vampire_defense_ml.c

ifneq (,$(wildcard ../contiki-ng/Makefile.include))
  CONTIKI = ../contiki-ng
else
  CONTIKI ?= /home/user/contiki-ng
endif

include $(CONTIKI)/Makefile.include
