CONTIKI_PROJECT = vampire_carousel vampire_stretch vampire_hybrid vampire_stealth

# Contiki-NG path (adjust if needed)
CONTIKI = ../../contiki-ng

# Include standard Contiki-NG Makefile
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
.PHONY: carousel stretch hybrid stealth

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

# Compile all
.PHONY: all
all: carousel stretch hybrid stealth
	@echo ""
	@echo "✅ All attack types compiled successfully!"
	@echo ""
