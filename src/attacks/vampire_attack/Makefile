CONTIKI_PROJECT = vampire_carousel vampire_stretch vampire_hybrid vampire_stealth vampire_coordinated vampire_switchable

# Contiki-NG path
CONTIKI = ../../contiki-ng

MAKE_MAC = MAKE_MAC_TSCH
MAKE_ROUTING = MAKE_ROUTING_RPL_LITE

# Orchestra scheduler for TSCH+RPL integration (MUST match nodes/Makefile)
MODULES += os/services/orchestra

# project-conf.h will provide additional TSCH config
all: $(CONTIKI_PROJECT)

# Include Contiki-NG Makefile
include $(CONTIKI)/Makefile.include

# Help target
.PHONY: help
help:
	@echo "=================================================="
	@echo "VAMPIRE ATTACK COMPILATION"
	@echo "=================================================="
	@echo ""
	@echo "Available targets:"
	@echo "  make all                    - Compile all attack types"
	@echo "  make carousel              - Compile carousel attack only"
	@echo "  make stretch               - Compile stretch attack only"
	@echo "  make hybrid                - Compile hybrid attack only"
	@echo "  make stealth               - Compile stealth attack only"
	@echo "  make coordinated           - Compile coordinated attack only"
	@echo "  make switchable            - Compile switchable attack node only"
	@echo ""
	@echo "Specify platform (default: sky):"
	@echo "  make TARGET=sky carousel"
	@echo "  make TARGET=cooja carousel"
	@echo ""
	@echo "Clean:"
	@echo "  make clean                 - Remove compiled files"
	@echo ""
	@echo "Example:"
	@echo "  make TARGET=sky carousel"
	@echo "  Output: vampire_carousel.sky"
	@echo ""
	@echo "=================================================="

# Individual targets
.PHONY: carousel stretch hybrid stealth coordinated switchable

carousel:
	@echo "Compiling Carousel Attack..."
	$(MAKE) vampire_carousel.$(TARGET)

stretch:
	@echo "Compiling Stretch Attack..."
	$(MAKE) vampire_stretch.$(TARGET)

hybrid:
	@echo "Compiling Hybrid Attack..."
	$(MAKE) vampire_hybrid.$(TARGET)

stealth:
	@echo "Compiling Stealth Attack..."
	$(MAKE) vampire_stealth.$(TARGET)

coordinated:
	@echo "Compiling Coordinated Attack..."
	$(MAKE) vampire_coordinated.$(TARGET)

switchable:
	@echo "Compiling Switchable Attack Node..."
	$(MAKE) vampire_switchable.$(TARGET)

# Compile all
.PHONY: all
all: carousel stretch hybrid stealth coordinated switchable
	@echo ""
	@echo "✅ All attack types compiled successfully!"
	@echo ""
