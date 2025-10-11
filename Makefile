# Makefile for managing Kubernetes manifests from Helm chart

# Variables
CHART_DIR = ./busybox-chart
BUILD_DIR = ./build
RELEASE_NAME = $(whoami)-N

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo ""
	@echo "📦 Build targets:"
	@echo "  build           - Generate Kubernetes manifests from Helm chart"
	@echo "  build-fast      - Build without cleaning first (faster)"
	@echo "  values          - Generate values files for all scenarios"
	@echo "  clean           - Remove the build directory"
	@echo ""
	@echo "🔍 Validation targets:"
	@echo "  validate        - Lint and validate the Helm chart"
	@echo "  show            - Preview what would be generated"
	@echo ""
	@echo "🚀 Deployment targets:"
	@echo "  install         - Deploy all resources to Kubernetes via helm"
	@echo ""
	@echo "🗑️  Cleanup targets:"
	@echo "  uninstall       - Remove all resources from via helm"
	@echo ""
	@echo "  help            - Show this help message"

# Clean target - removes the build directory
.PHONY: clean
clean:
	@echo "🧹 Cleaning build directory..."
	rm -rf $(BUILD_DIR)
	@echo "✅ Build directory cleaned"

# Build target - generates Kubernetes manifests
.PHONY: build
build: clean
	@echo "🏗️  Building Kubernetes manifests..."
	mkdir -p $(BUILD_DIR)
	helm template $(RELEASE_NAME) $(CHART_DIR) --output-dir $(BUILD_DIR)
	@echo "✅ Manifests generated in $(BUILD_DIR)"
	@echo ""
	@echo "📁 Generated files:"
	@find $(BUILD_DIR) -name "*.yaml" -type f | sort

# Build without cleaning first (for faster rebuilds)
.PHONY: build-fast
build-fast:
	@echo "⚡ Fast building Kubernetes manifests..."
	mkdir -p $(BUILD_DIR)
	helm template $(RELEASE_NAME) $(CHART_DIR) --output-dir $(BUILD_DIR) --replace
	@echo "✅ Manifests updated in $(BUILD_DIR)"

# Validate the chart before building
.PHONY: validate
validate:
	@echo "🔍 Validating Helm chart..."
	helm lint $(CHART_DIR)
	helm template $(RELEASE_NAME) $(CHART_DIR) --dry-run > /dev/null
	@echo "✅ Chart validation successful"

# Show what would be built without actually building
.PHONY: show
show:
	@echo "👀 Showing what would be generated..."
	helm template $(RELEASE_NAME) $(CHART_DIR)

.PHONY: install
install:
	./scripts/install.sh

.PHONY: uninstall
uninstall:
	./scripts/uninstall.sh

.PHONY: values
values:
	./scripts/generate-values.py
