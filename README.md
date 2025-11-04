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
python scenarios.py

# This creates values files in build/values/ for each scenario
```

The convention of the generated values filenames is `values-{release_name}.yaml`,
where the convention for release name is `np{nodepool_index}-w{workload_id}-r{replica_count}`.

### 4. Run a Test Scenario

```bash
# Install a scenario (e.g., C2)
python run-scenario.py C2

# Uninstall a scenario
python run-scenario.py C2 --uninstall
```

## Framework Architecture

### Core Components

- **`scenarios.py`**: Generates Helm values files for different test scenarios
- **`run-scenario.py`**: Installs/uninstalls scenarios and collects measurements
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
python scenarios.py
```

This creates values files in `build/values/MY_SCENARIO/` with different replica counts and configurations.

This is done automatically when running a scenario, but can be useful to do beforehand when creating new scenarios or adjusting the value generation logic.

### 3. Run the New Scenario

```bash
# Install the scenario
python run-scenario.py MY_SCENARIO

# Uninstall when done
python run-scenario.py MY_SCENARIO --uninstall

# Install with a custom prefix on all releases
python run-scenario.py MY_SCENARIO --release-prefix myusername
```

## Understanding Output Files

The framework generates detailed JSON measurement files in the `output/` directory. Each file contains:

### Basic Information

- **`args`**: Command-line arguments used
- **`timestamp`**: When the test was run
- **`install_time`**: Time taken to install/uninstall

### Performance Metrics

- **`postprocessed`**: Aggregated performance statistics
  - `jain_fairness_index_*`: Measures how evenly pods are distributed
  - `coefficient_of_variation_*`: Measures variability in pod distribution
  - `gini_coefficient_*`: Measures inequality in pod distribution
  - `node_skew_*`: Maximum difference between most and least loaded nodes
  - `nosed_used_*`: Statistics about nodes used

### Cluster State

- **`measurements_pre`**: Cluster state before workload deployment
- **`measurements_post`**: Cluster state after workload deployment
  - `cluster`: Node counts and eligibility
  - `deployments`: Per-deployment pod distribution statistics

### Example Output Analysis

```json
{
  "postprocessed": {
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

### Dry Run Mode

```bash
# Preview what would be installed without actually installing
python run-scenario.py C2 --dry-run
```

### Debug Mode

```bash
# Enable detailed logging
python run-scenario.py C2 --debug
```

### Local Template Rendering

```bash
# Render Helm templates locally without cluster access
python run-scenario.py C2 --render-locally
```

### Skip Installation

```bash
# Take measurements without installing workloads
python run-scenario.py C2 --skip-install
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

1. Update `generate-values.py` with new scenario definitions
2. Test with `--dry-run` first
3. Document the scenario purpose and expected behavior
4. Update the spreadsheet with new scenario information
