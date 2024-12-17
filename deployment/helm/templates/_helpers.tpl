{{/*
Expand the name of the chart.
*/}}
{{- define "anomalyPostProcessing.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "anomalyPostProcessing.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "anomalyPostProcessing.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create image pull secret for private docker registry
*/}}
{{- define "imagePullSecret" }}
{{- printf "{\"auths\": {\"%s\": {\"auth\": \"%s\"}}}" .Values.imageCredentials.registry (printf "%s:%s" .Values.imageCredentials.username .Values.imageCredentials.password | b64enc) | b64enc }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "anomalyPostProcessing.labels" -}}
helm.sh/chart: {{ include "anomalyPostProcessing.chart" . }}
{{ include "anomalyPostProcessing.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "anomalyPostProcessing.selectorLabels" -}}
app.kubernetes.io/name: {{ include "anomalyPostProcessing.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "anomalyPostProcessing.serviceAccountName" -}}
{{- include "anomalyPostProcessing.fullname" . }}
{{- end }}

{{/*
Derive redis service name
*/}}
{{- define "anomalyPostProcessing.redisServiceName" -}}
"valkey-primary"
{{- end }}

{{/*
Derive redis metrics service name
*/}}
{{- define "anomalyPostProcessing.redisMetricsServiceName" -}}
{{- printf "%s-%s" .Release.Name "metrics-server" -}}
{{- end }}

{{/*
Hard-code Redis service port (for now)
*/}}
{{- define "anomalyPostProcessing.redisServicePort" -}}
"6379"
{{- end }}

{{/*
Derive redis metrics service name
*/}}
{{- define "anomalyPostProcessing.nodeExporterServiceName" -}}
{{- printf "%s-%s" .Release.Name "nodeexporter" -}}
{{- end }}

{{/*
Derive prometheus service name
*/}}
{{- define "anomalyPostProcessing.prometheusServiceName" -}}
{{- printf "%s-%s" .Release.Name "prometheus-server" -}}
{{- end }}

{{/*
Derive minio service name
*/}}
{{- define "anomalyPostProcessing.minioEndpoint" -}}
{{- printf "%s-%s" .Release.Name "minio:9000" -}}
{{- end }}
