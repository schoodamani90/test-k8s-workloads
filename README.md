# Multi-Namespace Helm Chart Example

This repository demonstrates how to create a Helm chart that can deploy resources across multiple namespaces. This is useful for scenarios like multi-tenant applications, deploying to multiple environments, or cross-cutting services.

## Features

- ✅ Deploy to multiple namespaces from a single chart
- ✅ Automatic namespace creation with labels and annotations
- ✅ Per-namespace configuration overrides
- ✅ Backward compatibility with single-namespace deployments
- ✅ Service account creation per namespace
- ✅ Resource customization per namespace

## Chart Structure

```
busybox-chart/
├── Chart.yaml                      # Chart metadata
├── values.yaml                     # Default values with multi-namespace config
├── values-single-namespace.yaml    # Example: Traditional single namespace
├── values-multi-env.yaml          # Example: Multi-environment deployment
├── values-multi-tenant.yaml       # Example: Multi-tenant deployment
└── templates/
    ├── _helpers.tpl               # Helper templates for namespace logic
    ├── namespace.yaml             # Automatic namespace creation
    ├── deployment.yaml            # Multi-namespace aware deployments
    ├── service.yaml               # Services for each namespace
    ├── serviceaccount.yaml        # Service accounts per namespace
    └── NOTES.txt                  # Deployment instructions
```

## Usage Examples

### 1. Multi-Environment Deployment

Deploy the same application to dev, staging, and prod namespaces:

```bash
# Install with multi-environment configuration
helm install my-app ./busybox-chart -f values-multi-env.yaml

# This creates:
# - Namespaces: my-app-dev, my-app-staging, my-app-prod
# - Deployments with different replica counts per environment
# - Services for each deployment
# - Service accounts per namespace
```

### 2. Multi-Tenant Deployment

Deploy to multiple tenant namespaces with different resource allocations:

```bash
# Install with multi-tenant configuration
helm install tenant-app ./busybox-chart -f values-multi-tenant.yaml

# This creates resources in:
# - tenant-acme (premium tier)
# - tenant-globex (standard tier)
# - tenant-initech (premium tier)
```

### 3. Single Namespace (Traditional)

For backward compatibility, disable multi-namespace mode:

```bash
# Traditional single-namespace deployment
helm install my-app ./busybox-chart -f values-single-namespace.yaml --namespace my-namespace
```

### 4. Custom Configuration

Create your own values file:

```yaml
multiNamespace:
  enabled: true
  createNamespaces: true
  namespaces:
    - name: "frontend"
      labels:
        tier: "frontend"
    - name: "backend"
      labels:
        tier: "backend"

namespaceOverrides:
  backend:
    replicaCount: 3
    resources:
      requests:
        cpu: 200m
        memory: 256Mi
```

## Configuration Options

### Multi-Namespace Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `multiNamespace.enabled` | Enable multi-namespace deployment | `true` |
| `multiNamespace.createNamespaces` | Auto-create namespaces | `true` |
| `multiNamespace.namespaces` | List of namespaces to deploy to | See values.yaml |

### Per-Namespace Overrides

Use `namespaceOverrides` to customize settings for specific namespaces:

```yaml
namespaceOverrides:
  production:
    replicaCount: 5
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
  development:
    replicaCount: 1
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
```

## Verification Commands

After deployment, verify the resources:

```bash
# Check all namespaces
kubectl get namespaces | grep -E "(dev|staging|prod)"

# Check deployments across namespaces
kubectl get deployments --all-namespaces -l app.kubernetes.io/name=busybox-chart

# Check services
kubectl get services --all-namespaces -l app.kubernetes.io/name=busybox-chart

# Check pods in specific namespace
kubectl get pods -n my-app-dev -l app.kubernetes.io/instance=my-app
```

## Advanced Use Cases

### 1. Cross-Namespace Service Discovery

Services are created in each namespace, so applications can communicate within their namespace or across namespaces using FQDN:

```
my-app-dev.my-app-dev.svc.cluster.local
my-app-staging.my-app-staging.svc.cluster.local
```

### 2. Network Policies

Add namespace-specific network policies:

```yaml
# In values file
namespaceOverrides:
  production:
    networkPolicy:
      enabled: true
      ingress:
        - from:
          - namespaceSelector:
              matchLabels:
                name: production
```

### 3. RBAC

Service accounts are created per namespace, enabling namespace-specific RBAC:

```bash
# Grant permissions to service account in specific namespace
kubectl create rolebinding my-app-binding \
  --clusterrole=view \
  --serviceaccount=production:my-app \
  --namespace=production
```

## Cleanup

```bash
# Uninstall the release (removes all resources across namespaces)
helm uninstall my-app

# Manually remove namespaces if needed
kubectl delete namespace my-app-dev my-app-staging my-app-prod
```

## Template Logic

The chart uses several helper templates:

- `busybox-chart.namespaces`: Gets list of target namespaces
- `busybox-chart.replicaCount`: Gets replica count for specific namespace
- `busybox-chart.resources`: Gets resources for specific namespace
- `busybox-chart.namespacedName`: Generates namespace-specific resource names

This ensures consistent naming and configuration across all resources while allowing per-namespace customization.

# Helm Approach

1. `helm package`, this will create `busybox-chart-0.1.0.tgz`
2. (Optional) create `values-my-install.yaml` with any tweakes
3. `helm install my-busybox-install busybox-chart-0.1.0.tgz --values values-my-install.yaml --namespace my-namepsace --create-namespace --atomic`
4. Repeat steps 2-3 for additional namespaces/experiment permutations.
5. Cleanup. `helm uninstall my-busybox-install --namespace my-namespace`

See `scripts/install.sh` for concrete examples.
