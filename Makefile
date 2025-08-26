# Makefile for managing Kubernetes manifests from Helm chart

# Variables
CHART_DIR = ./busybox-chart
BUILD_DIR = ./build
RELEASE_NAME = my-app

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo ""
	@echo "📦 Build targets:"
	@echo "  build           - Generate Kubernetes manifests from Helm chart"
	@echo "  build-fast      - Build without cleaning first (faster)"
	@echo "  clean           - Remove the build directory"
	@echo ""
	@echo "🔍 Validation targets:"
	@echo "  validate        - Lint and validate the Helm chart"
	@echo "  show            - Preview what would be generated"
	@echo ""
	@echo "🚀 Deployment targets:"
	@echo "  deploy                - Deploy all resources to Kubernetes"
	@echo "  deploy-namespaces     - Deploy only namespaces"
	@echo "  deploy-services       - Deploy only services"  
	@echo "  deploy-deployments    - Deploy only deployments"
	@echo "  deploy-ordered        - Deploy in order (ns→svc→deploy)"
	@echo ""
	@echo "🗑️  Cleanup targets:"
	@echo "  undeploy              - Remove all resources from Kubernetes"
	@echo "  undeploy-deployments  - Remove only deployments"
	@echo "  undeploy-services     - Remove only services"
	@echo "  undeploy-namespaces   - Remove only namespaces (⚠️  removes everything)"
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

# Deploy the manifests to Kubernetes (requires kubectl)
.PHONY: deploy
deploy: build
	@echo "🚀 Deploying manifests to Kubernetes..."
	@echo "📦 Creating namespaces first..."
	kubectl apply -f $(BUILD_DIR)/busybox-chart/templates/namespace.yaml
	@echo "⏳ Waiting 5 seconds for namespaces to be ready..."
	sleep 5
	@echo "🚀 Deploying remaining resources..."
	kubectl apply -f $(BUILD_DIR)/busybox-chart/templates/service.yaml
	kubectl apply -f $(BUILD_DIR)/busybox-chart/templates/deployment.yaml
	@echo "✅ Deployment complete"

# Deploy only namespaces
.PHONY: deploy-namespaces
deploy-namespaces: build
	@echo "🚀 Deploying namespaces to Kubernetes..."
	kubectl apply -f $(BUILD_DIR)/busybox-chart/templates/namespace.yaml
	@echo "✅ Namespaces deployed"

# Deploy only services
.PHONY: deploy-services
deploy-services: build
	@echo "🚀 Deploying services to Kubernetes..."
	kubectl apply -f $(BUILD_DIR)/busybox-chart/templates/service.yaml
	@echo "✅ Services deployed"

# Deploy only deployments
.PHONY: deploy-deployments
deploy-deployments: build
	@echo "🚀 Deploying deployments to Kubernetes..."
	kubectl apply -f $(BUILD_DIR)/busybox-chart/templates/deployment.yaml
	@echo "✅ Deployments deployed"

# Deploy in order (namespaces first, then services, then deployments)
.PHONY: deploy-ordered
deploy-ordered: deploy-namespaces deploy-services deploy-deployments
	@echo "✅ All resources deployed in order"

# Remove resources from Kubernetes
.PHONY: undeploy
undeploy:
	@echo "🗑️  Removing resources from Kubernetes..."
	kubectl delete -f $(BUILD_DIR)/busybox-chart/templates/ --ignore-not-found=true
	@echo "✅ Resources removed"

# Remove only deployments
.PHONY: undeploy-deployments
undeploy-deployments:
	@echo "🗑️  Removing deployments from Kubernetes..."
	kubectl delete -f $(BUILD_DIR)/busybox-chart/templates/deployment.yaml --ignore-not-found=true
	@echo "✅ Deployments removed"

# Remove only services
.PHONY: undeploy-services
undeploy-services:
	@echo "🗑️  Removing services from Kubernetes..."
	kubectl delete -f $(BUILD_DIR)/busybox-chart/templates/service.yaml --ignore-not-found=true
	@echo "✅ Services removed"

# Remove only namespaces (this will remove everything in those namespaces)
.PHONY: undeploy-namespaces
undeploy-namespaces:
	@echo "🗑️  Removing namespaces from Kubernetes..."
	kubectl delete -f $(BUILD_DIR)/busybox-chart/templates/namespace.yaml --ignore-not-found=true
	@echo "✅ Namespaces removed"