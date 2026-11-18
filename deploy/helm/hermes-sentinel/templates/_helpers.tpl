{{- define "sentinel.name" -}}hermes-sentinel{{- end -}}

{{- define "sentinel.fullname" -}}
{{- if contains "hermes-sentinel" .Release.Name -}}{{ .Release.Name | trunc 50 | trimSuffix "-" }}
{{- else -}}{{ printf "%s-hermes-sentinel" .Release.Name | trunc 50 | trimSuffix "-" }}{{- end -}}
{{- end -}}

{{- define "sentinel.labels" -}}
app.kubernetes.io/name: {{ include "sentinel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "sentinel.selector" -}}
app.kubernetes.io/name: {{ include "sentinel.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "sentinel.serviceAccount" -}}
{{- default (include "sentinel.fullname" .) .Values.serviceAccount.name -}}
{{- end -}}

{{- define "sentinel.secretName" -}}
{{- default (printf "%s-env" (include "sentinel.fullname" .)) .Values.central.existingSecret -}}
{{- end -}}

{{- define "sentinel.backendImage" -}}
{{ .Values.image.backend.repository }}:{{ default .Chart.AppVersion .Values.image.backend.tag }}
{{- end -}}
