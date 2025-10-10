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
Generate namespace-specific resource name
*/}}
{{- define "busybox-chart.namespacedName" -}}
{{- $namespace := .namespace }}
{{- $root := .root }}
{{- $baseName := include "busybox-chart.fullname" $root }}
{{- printf "%s-%s" $namespace $baseName }}
{{- end }}
