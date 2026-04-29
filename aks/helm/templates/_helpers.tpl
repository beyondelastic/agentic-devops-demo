{{- define "trial-matcher.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "trial-matcher.image" -}}
{{- printf "%s/%s:%s" .registry .name .tag -}}
{{- end -}}
