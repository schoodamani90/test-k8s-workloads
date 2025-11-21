# Kubernetes Workload Testing Framework

This repository provides a comprehensive framework for testing Kubernetes workload distribution and scheduling behavior using Helm charts. The framework supports various scheduling mechanisms and generates detailed performance measurements.

## Overview

The testing framework uses Helm to install and manage Kubernetes workloads across different scenarios. It generates values files for various test scenarios and measures cluster behavior during workload deployment.

## Quick Start

### 1. Prerequisites

- Python 3.7+
- Helm 3.x
- kubectl configured for cosmos-dev-cosmos

### 2. Install Dependencies

```bash
cd scripts
source setup.sh
```

### 3. Generate Test Scenarios

```bash
# Generate all predefined scenarios
python scripts/scenarios.py

# This creates values files in build/values/ for each scenario
```

The convention of the generated values filenames is `values-{release_name}.yaml`,
where the convention for release name is `np{nodepool_index}-w{workload_id}-r{replica_count}`.

### 4. Run a Test Scenario

```bash
# Install a scenario (e.g., C2) in a namespace
python scripts/experiment.py C2 --namespace my-namespace

# Uninstall a scenario
python scripts/experiment.py C2 --namespace my-namespace --action uninstall

# Restart deployments in a scenario
python scripts/experiment.py C2 --namespace my-namespace --action restart
```

## Framework Architecture

### Core Components

- **`scenarios.py`**: Generates Helm values files for different test scenarios
- **`experiment.py`**: Installs/uninstalls scenarios and collects measurements
- **`busybox-chart/`**: Helm chart for deploying test workloads
- **`output/`**: JSON files containing detailed performance measurements

### Test Scenarios

The official list of scenarios is tracked [in this spreadsheet](https://docs.google.com/spreadsheets/d/1bwdC6Ll_iOYvhCIqxCnHrUGn-GX6dtR2EKRf7zNB-5c/edit).

## Adding New Scenarios

### 1. Edit `scenarios.py`

Add a new scenario to the `SCENARIOS` list:

```python
Scenario(
    name="MY_SCENARIO",
    mechanism=Mechanism.POD_ANTI_AFFINITY,
    nodepool_count=2,
    workloads_per_nodepool=[5, 8],
    replicas_min=10,
    replicas_max=100,
)
```

### 2. (Optional) Generate Values Files

```bash
python scripts/scenarios.py
```

This creates values files in `build/values/MY_SCENARIO/` with different replica counts and configurations.

This is done automatically when running a scenario, but can be useful to do beforehand when creating new scenarios or adjusting the value generation logic.

### 3. Run the New Scenario

```bash
# Install the scenario in a namespace
python scripts/experiment.py MY_SCENARIO --namespace my-namespace

# Uninstall when done
python scripts/experiment.py MY_SCENARIO --namespace my-namespace --action uninstall

# Install with a custom prefix on all releases
python scripts/experiment.py MY_SCENARIO --namespace my-namespace --release-prefix myusername
```

Debug any issues by running the above command with the `--debug` flag.


## Understanding Output Files

The framework generates detailed JSON measurement files in the `output/` directory. Files are named using the pattern `{scenario_name}-{timestamp}.json` (e.g., `C2-2025-10-27T16:41:21.json`) and are organized in subdirectories by scenario name.

Each file contains:

### Basic Information

- **`args`**: Command-line arguments used (including scenario name and action)
- **`cluster`**: The cluster context name where the experiment was run
- **`start_time`**: ISO timestamp when the test started
- **`elapsed_time`**: Time taken to perform the action (install/uninstall/restart)

### Performance Metrics

- **`postprocessed_data`**: Aggregated performance statistics
  - `jain_fairness_index_mean` / `jain_fairness_index_median`: Measures how evenly pods are distributed
  - `coefficient_of_variation_mean` / `coefficient_of_variation_median`: Measures variability in pod distribution
  - `gini_coefficient_mean` / `gini_coefficient_median`: Measures inequality in pod distribution
  - `node_skew_mean` / `node_skew_median` / `node_skew_max`: Maximum difference between most and least loaded nodes
  - `node_skew_percentage_mean` / `node_skew_percentage_median` / `node_skew_percentage_max`: Node skew as percentage
  - `nosed_used_avg` / `nosed_used_median` / `nosed_used_max` / `nosed_used_min`: Statistics about nodes used
  - `scale_direction` / `scale_amount` / `scale_percentage`: Cluster scaling information (if pre-measurements available)

### Cluster State

- **`measurements_taken`**: Array of measurement snapshots
  - First element: Cluster state before workload deployment (if available)
  - Second element: Cluster state after workload deployment
  - Each measurement contains:
    - `cluster`: Node counts and eligibility
    - `deployments`: Per-deployment pod distribution statistics

### Example Output Analysis

```json
{
  "postprocessed_data": {
    "jain_fairness_index_mean": 0.584,
    "coefficient_of_variation_mean": 0.906,
    "gini_coefficient_mean": 0.425,
    "node_skew_mean": 13.9
  }
}
```

- **Jain Fairness Index**: 0.584 (closer to 1.0 = more fair distribution)
- **Coefficient of Variation**: 0.906 (lower = more consistent distribution)
- **Gini Coefficient**: 0.425 (lower = more equal distribution)
- **Node Skew**: 13.9 (difference between most/least loaded nodes)

## Advanced Usage

### Required Arguments

- **`--namespace` / `-ns`**: The namespace to install the scenario into (required)

### Action Arguments

- **`--action` / `-a`**: The action to perform (default: `install`)
  - `install`: Install the scenario
  - `uninstall`: Uninstall the scenario
  - `restart`: Restart all deployments in the scenario
  - `none`: Skip installation/uninstallation (only take measurements)

### General Arguments

- **`--debug` / `-d`**: Enable detailed logging
- **`--no-print` / `-np`**: Suppress measurement visualizations in console output
- **`--dry-run`**: Preview what would be installed without actually installing

### Template and Value Generation

- **`--render-locally`**: Render Helm templates locally without cluster access
- **`--skip-value-generation`**: Skip value generation (useful for testing manually crafted values files)

### Release Naming

- **`--release-prefix` / `-rp`**: Prefix all generated release names with this string (optional)

### Examples

```bash
# Preview what would be installed without actually installing
python scripts/experiment.py C2 --namespace my-namespace --dry-run

# Enable detailed logging
python scripts/experiment.py C2 --namespace my-namespace --debug

# Render Helm templates locally without cluster access
python scripts/experiment.py C2 --namespace my-namespace --render-locally

# Take measurements without installing workloads
python scripts/experiment.py C2 --namespace my-namespace --action none

# Suppress console output visualizations
python scripts/experiment.py C2 --namespace my-namespace --no-print
```

## Collecting Measurements from Existing Deployments

For analyzing real deployments (as opposed to synthetic test scenarios), use `collect.py`:

```bash
# Collect measurements from default namespaces on default cluster
python scripts/collect.py

# Collect from specific namespaces
python scripts/collect.py --namespaces namespace1 namespace2

# Collect from a different cluster
python scripts/collect.py --cluster-context "arn:aws:eks:us-east-1:906324658258:cluster/prod-live-main"
```

## Helm Chart Details

The `busybox-chart/` directory contains a Helm chart that:

- Deploys busybox containers as test workloads
- Supports various scheduling mechanisms (node selectors, anti-affinity, etc.)
- Configures resource requests and limits

## Troubleshooting

### Common Issues

1. **Cluster Connection**: Ensure kubectl is configured correctly. Run `scc -c cosmos-dev-cosmos`.
2. **Helm Not Found**: Install Helm 3.x and ensure it's in PATH
3. **Permission Denied**: Ensure your kubeconfig has sufficient permissions
4. **Resource Limits**: Check cluster has enough resources for test scenarios

## Contributing

When adding new scenarios or mechanisms:

1. Update `scenarios.py` with new scenario definitions
2. Test with `--dry-run` first
3. Document the scenario purpose and expected behavior
4. Update the spreadsheet with new scenario information
