helm uninstall bw-busybox-1 --namespace bw-1
helm uninstall bw-busybox-2 --namespace bw-2
helm uninstall bw-busybox-3 --namespace bw-3

kubectl delete namespace bw-1 bw-2 bw-3
