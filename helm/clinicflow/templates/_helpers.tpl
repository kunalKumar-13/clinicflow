{{/* Shared naming and label helpers, so every object is labelled consistently. */}}

{{- define "clinicflow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "clinicflow.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "clinicflow.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "clinicflow.labels" -}}
app.kubernetes.io/name: {{ include "clinicflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* The database URL the backend uses, built from the postgres values. */}}
{{- define "clinicflow.databaseUrl" -}}
{{- $pw := required "postgres.password is required: --set postgres.password=$(openssl rand -hex 16)" .Values.postgres.password -}}
{{- printf "postgresql+psycopg://%s:%s@%s-postgres:5432/%s" .Values.postgres.user $pw (include "clinicflow.fullname" .) .Values.postgres.database -}}
{{- end -}}
