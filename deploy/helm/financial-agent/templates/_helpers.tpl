{{/*
Expand the name of the chart.
*/}}
{{- define "financial-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "financial-agent.fullname" -}}
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
{{- define "financial-agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
Templates pass a dict like (dict "root" . "component" "backend").
*/}}
{{- define "financial-agent.labels" -}}
{{- $root := .root }}
{{- $component := default "" .component }}
helm.sh/chart: {{ include "financial-agent.chart" $root }}
app.kubernetes.io/name: {{ include "financial-agent.name" $root }}
app.kubernetes.io/instance: {{ $root.Release.Name }}
{{- if $component }}
app.kubernetes.io/component: {{ $component }}
{{- end }}
{{- if $root.Chart.AppVersion }}
app.kubernetes.io/version: {{ $root.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ $root.Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "financial-agent.selectorLabels" -}}
{{- $root := .root }}
{{- $component := default "" .component }}
app.kubernetes.io/name: {{ include "financial-agent.name" $root }}
app.kubernetes.io/instance: {{ $root.Release.Name }}
{{- if $component }}
app.kubernetes.io/component: {{ $component }}
{{- end }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "financial-agent.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "financial-agent.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Secret name (existing external secret or chart-generated secret)
*/}}
{{- define "financial-agent.secretName" -}}
{{- if .Values.externalSecrets.existingSecretName }}
{{- .Values.externalSecrets.existingSecretName }}
{{- else }}
{{- include "financial-agent.fullname" . }}
{{- end }}
{{- end }}

{{/*
Image reference for a component.
Usage: {{ include "financial-agent.image" (list . "backend") }}
*/}}
{{- define "financial-agent.image" -}}
{{- $root := index . 0 }}
{{- $component := index . 1 }}
{{- $values := index $root.Values $component }}
{{- $repository := $values.image.repository }}
{{- $tag := $values.image.tag | default $root.Chart.AppVersion }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}

{{/*
Image pull policy for a component.
Usage: {{ include "financial-agent.imagePullPolicy" (list . "backend") }}
*/}}
{{- define "financial-agent.imagePullPolicy" -}}
{{- $root := index . 0 }}
{{- $component := index . 1 }}
{{- $values := index $root.Values $component }}
{{- $values.image.pullPolicy }}
{{- end }}
