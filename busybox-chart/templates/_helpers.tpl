{{/*
Expand the name of the chart.
*/}}
{{- define "busybox-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "busybox-chart.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "busybox-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "busybox-chart.labels" -}}
helm.sh/chart: {{ include "busybox-chart.chart" . }}
{{ include "busybox-chart.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "busybox-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "busybox-chart.name" . }}
{{- end }}

{{/*
Multi-namespace helpers
*/}}

{{/*
Get list of namespaces to deploy to
*/}}
{{- define "busybox-chart.namespaces" -}}
{{- range .Values.multiNamespace.namespaces }}
{{- .name }}
{{- end }}
{{- end }}

{{/*
Get replica count for a specific namespace
*/}}
{{- define "busybox-chart.replicaCount" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $override := index $root.Values.namespaceOverrides $namespace | default dict }}
{{- if $override.replicaCount }}
{{- $override.replicaCount }}
{{- else if $root.Values.global.replicaCount }}
{{- $root.Values.global.replicaCount }}
{{- else }}
{{- $root.Values.replicaCount }}
{{- end }}
{{- end }}

{{/*
Create a context for namespace-specific resources
*/}}
{{- define "busybox-chart.namespaceContext" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $context := dict "Values" $root.Values "Chart" $root.Chart "Release" $root.Release "Template" $root.Template }}
{{- $context = merge $context (dict "namespace" $namespace) }}
{{- $context }}
{{- end }}

{{/*
Get nodeSelector for a specific namespace
*/}}
{{- define "busybox-chart.nodeSelector" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $override := index $root.Values.namespaceOverrides $namespace | default dict }}
{{- if $override.nodeSelector }}
{{- toYaml $override.nodeSelector }}
{{- else }}
{{- toYaml $root.Values.nodeSelector }}
{{- end }}
{{- end }}

{{/*
Get affinity for a specific namespace
*/}}
{{- define "busybox-chart.affinity" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $override := index $root.Values.namespaceOverrides $namespace | default dict }}
{{- if $override.affinity }}
{{- toYaml $override.affinity }}
{{- else }}
{{- toYaml $root.Values.affinity }}
{{- end }}
{{- end }}

{{/*
Get tolerations for a specific namespace
*/}}
{{- define "busybox-chart.tolerations" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $override := index $root.Values.namespaceOverrides $namespace | default dict }}
{{- if $override.tolerations }}
{{- toYaml $override.tolerations }}
{{- else }}
{{- toYaml $root.Values.tolerations }}
{{- end }}
{{- end }}

{{/*
Get topology spread constraints for a specific namespace
*/}}
{{- define "busybox-chart.topologySpreadConstraints" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $override := index $root.Values.namespaceOverrides $namespace | default dict }}
{{- if $override.topologySpreadConstraints }}
{{- toYaml $override.topologySpreadConstraints }}
{{- else }}
{{- toYaml $root.Values.topologySpreadConstraints }}
{{- end }}
{{- end }}

{{/*
Generate namespace-specific resource name
*/}}
{{- define "busybox-chart.namespacedName" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $baseName := include "busybox-chart.fullname" $root }}
{{- printf "%s-%s" $namespace $baseName }}
{{- end }}