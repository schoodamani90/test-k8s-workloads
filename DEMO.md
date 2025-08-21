# Multi-Namespace Helm Chart Demo

## Quick Demo Commands

Here are some commands to test the multi-namespace Helm chart functionality:

### 1. Default Multi-Namespace Deployment
```bash
# Template render with default values (dev, staging, prod namespaces)
helm template my-app ./busybox-chart --dry-run

# Shows:
# - 3 namespaces created with labels
# - Service accounts in each namespace  
# - Services with namespace-specific names
# - Deployments with different replica counts per environment
```

### 2. Multi-Tenant Deployment
```bash
# Template render for multi-tenant scenario
helm template tenant-app ./busybox-chart -f ./busybox-chart/values-multi-tenant.yaml --dry-run

# Creates tenant namespaces:
# - tenant-acme (premium tier, 3 replicas, high resources)
# - tenant-globex (standard tier, 2 replicas, standard resources)  
# - tenant-initech (premium tier, 3 replicas, high resources)
```

### 3. Multi-Environment Deployment  
```bash
# Template render for environment-based deployment
helm template env-app ./busybox-chart -f ./busybox-chart/values-multi-env.yaml --dry-run

# Creates environment namespaces:
# - my-app-dev (1 replica, minimal resources)
# - my-app-staging (2 replicas, medium resources)
# - my-app-prod (3 replicas, high resources)
```

### 4. Single Namespace (Traditional)
```bash
# Template render for traditional single-namespace deployment
helm template single-app ./busybox-chart -f ./busybox-chart/values-single-namespace.yaml --dry-run

# Shows traditional Helm behavior with no multi-namespace logic
```

### 5. Actual Deployment (if you have a Kubernetes cluster)
```bash
# Deploy to actual cluster
helm install my-release ./busybox-chart

# Check what was created
kubectl get namespaces | grep -E "(dev|staging|prod)"
kubectl get deployments --all-namespaces -l app.kubernetes.io/name=busybox-chart
kubectl get services --all-namespaces -l app.kubernetes.io/name=busybox-chart

# Cleanup
helm uninstall my-release
kubectl delete namespace dev staging prod
```

## Key Features Demonstrated

✅ **Multi-namespace deployment from single chart**
✅ **Automatic namespace creation with custom labels**  
✅ **Per-namespace configuration overrides**
✅ **Namespace-specific resource names to avoid conflicts**
✅ **Backward compatibility with single-namespace deployments**
✅ **Service accounts created per namespace**
✅ **Environment variables injected with namespace info**

## Chart Architecture

The chart uses several helper templates to manage multi-namespace complexity:

- `busybox-chart.replicaCount`: Gets replica count for specific namespace
- `busybox-chart.resources`: Gets resources for specific namespace  
- `busybox-chart.namespacedName`: Generates namespace-specific names
- `busybox-chart.namespaceContext`: Creates context for namespace templating

This pattern can be extended to other Kubernetes resources like ConfigMaps, Secrets, Ingress, etc.