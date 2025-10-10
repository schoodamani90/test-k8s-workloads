#!/usr/bin/env bash
current_context=$(kubectl config current-context)
if [ "$current_context" != "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos" ]; then
    echo "Not using the correct context. scc to cosmos-dev-cosmos"
    exit 1
fi
helm install bw-busybox-1 ./busybox-chart -f values-bw-1.yaml --namespace bw-1 --create-namespace
helm install bw-busybox-2 ./busybox-chart -f values-bw-2.yaml --namespace bw-2 --create-namespace
helm install bw-busybox-3 ./busybox-chart -f values-bw-3.yaml --namespace bw-3 --create-namespace
