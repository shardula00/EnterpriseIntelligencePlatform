/** Convenience aliases onto the generated OpenAPI component schemas. */
import type { components } from './schema'

export type DatasetSummary = components['schemas']['DatasetSummary']
export type DatasetDetail = components['schemas']['DatasetDetail']
export type ColumnInfo = components['schemas']['ColumnInfo']
export type QualityIssue = components['schemas']['QualityIssueOut']
export type QualityReport = components['schemas']['QualityReportOut']
export type LineageEvent = components['schemas']['LineageEventOut']
export type Lineage = components['schemas']['LineageOut']
export type Preview = components['schemas']['PreviewOut']
export type KpiValue = components['schemas']['KpiValueOut']
export type KpiSummary = components['schemas']['KpiSummaryOut']
export type BreakdownItem = components['schemas']['BreakdownItemOut']
export type Breakdown = components['schemas']['BreakdownOut']
export type TrendPoint = components['schemas']['TrendPointOut']
export type Trend = components['schemas']['TrendOut']

// Auth / RBAC / audit (Phase 4)
export type CurrentUser = components['schemas']['UserOut']
export type TokenResponse = components['schemas']['TokenResponse']
export type UserAdmin = components['schemas']['UserAdminOut']
export type RoleInfo = components['schemas']['RoleOut']
export type PermissionInfo = components['schemas']['PermissionOut']
export type AuditLogEntry = components['schemas']['AuditLogOut']
export type AuditLogPage = components['schemas']['AuditLogPage']

/** The three fixed role names - kept as a literal union, not just `string`,
 * so the frontend can't reference a role the backend doesn't know about. */
export type RoleName = 'ADMIN' | 'ANALYST' | 'VIEWER'

/** Every permission the backend's catalog defines - see
 * backend/app/rbac/seed.py. Kept as a literal union for the same reason. */
export type PermissionName =
  | 'dataset:read'
  | 'dataset:create'
  | 'dataset:delete'
  | 'dashboard:read'
  | 'dashboard:configure'
  | 'user:read'
  | 'user:create'
  | 'user:update'
  | 'user:delete'
  | 'audit:read'
  | 'ml:read'
  | 'ml:train'
  | 'ml:predict'
  | 'mlops:read'
  | 'mlops:evaluate'
  | 'mlops:promote'
  | 'rag:read'
  | 'rag:upload'
  | 'rag:query'
  | 'analytics:read'
  | 'analytics:query'

// ---------------------------------------------------------------------------
// Classical ML (Phase 5)
// ---------------------------------------------------------------------------

export type TaskSuitability = components['schemas']['TaskSuitabilityOut']
/** No standalone "TaskType" schema exists - Pydantic's Literal type alias
 * gets inlined wherever it's used rather than named, so this is derived
 * from one of those usage sites instead. */
export type MlTaskType = TaskSuitability['task_type']
export type DatasetSuitability = components['schemas']['DatasetSuitabilityOut']

export type ClassificationTrainRequest = components['schemas']['ClassificationTrainRequest']
export type ForecastTrainRequest = components['schemas']['ForecastTrainRequest']
export type SegmentationTrainRequest = components['schemas']['SegmentationTrainRequest']
export type AnomalyTrainRequest = components['schemas']['AnomalyTrainRequest']

export type CandidateModelMetrics = components['schemas']['CandidateModelMetrics']
export type FeatureImportance = components['schemas']['FeatureImportanceOut']

export type ConfusionMatrix = components['schemas']['ConfusionMatrixOut']
export type ClassificationSamplePrediction = components['schemas']['ClassificationSamplePrediction']
export type ClassificationResults = components['schemas']['ClassificationResultsOut']

export type TimeSeriesPoint = components['schemas']['TimeSeriesPointOut']
export type ForecastPoint = components['schemas']['ForecastPointOut']
export type ForecastResults = components['schemas']['ForecastResultsOut']

export type ClusterProfile = components['schemas']['ClusterProfileOut']
export type SegmentationResults = components['schemas']['SegmentationResultsOut']

export type AnomalyRecord = components['schemas']['AnomalyRecordOut']
export type AnomalyResults = components['schemas']['AnomalyResultsOut']

export type MLRun = components['schemas']['MLRunOut']
export type MLRunResults = components['schemas']['MLRunResultsOut']
export type PredictionResponse = components['schemas']['PredictionResponseOut']

export type ClassificationPrediction = components['schemas']['ClassificationPredictionOut']
export type SegmentationPrediction = components['schemas']['SegmentationPredictionOut']
export type AnomalyPrediction = components['schemas']['AnomalyPredictionOut']

/** Narrows MLRunResults.results to the shape matching its own task_type -
 * the union isn't discriminated at the schema level (see
 * backend/app/ml/schemas.py's comment on MLRunResultsOut), so callers
 * narrow using the sibling `run.task_type` field instead. */
export function isClassificationResults(
  run: MLRunResults,
): run is MLRunResults & { results: ClassificationResults } {
  return run.run.task_type === 'classification'
}

export function isForecastResults(
  run: MLRunResults,
): run is MLRunResults & { results: ForecastResults } {
  return run.run.task_type === 'forecasting'
}

export function isSegmentationResults(
  run: MLRunResults,
): run is MLRunResults & { results: SegmentationResults } {
  return run.run.task_type === 'segmentation'
}

export function isAnomalyResults(
  run: MLRunResults,
): run is MLRunResults & { results: AnomalyResults } {
  return run.run.task_type === 'anomaly_detection'
}

/** Same narrowing pattern for PredictionResponse.predictions - see the
 * comment above. */
export function isClassificationPredictions(
  response: PredictionResponse,
): response is PredictionResponse & { predictions: ClassificationPrediction[] } {
  return response.task_type === 'classification'
}

export function isForecastPredictions(
  response: PredictionResponse,
): response is PredictionResponse & { predictions: ForecastPoint[] } {
  return response.task_type === 'forecasting'
}

export function isSegmentationPredictions(
  response: PredictionResponse,
): response is PredictionResponse & { predictions: SegmentationPrediction[] } {
  return response.task_type === 'segmentation'
}

export function isAnomalyPredictions(
  response: PredictionResponse,
): response is PredictionResponse & { predictions: AnomalyPrediction[] } {
  return response.task_type === 'anomaly_detection'
}

// ---------------------------------------------------------------------------
// MLOps: model registry, drift detection, performance monitoring (Phase 6)
// ---------------------------------------------------------------------------

export type ModelVersion = components['schemas']['ModelVersionOut']
export type ModelVersionDetail = components['schemas']['ModelVersionDetailOut']
/** No standalone "LifecycleStatus" schema exists, same reasoning as
 * MlTaskType above - derived from a real usage site instead. */
export type LifecycleStatus = ModelVersion['status']

export type FeatureDrift = components['schemas']['FeatureDriftOut']
export type DriftResult = components['schemas']['DriftResultOut']
export type DriftStatus = DriftResult['overall_status']

export type PerformanceCheck = components['schemas']['PerformanceCheckOut']
export type PerformanceStatus = PerformanceCheck['status']

export type MonitoringEvent = components['schemas']['MonitoringEventOut']
export type MonitoringSeverity = MonitoringEvent['severity']

// ---------------------------------------------------------------------------
// Enterprise RAG: documents, chunks, query (Phase 7)
// ---------------------------------------------------------------------------

export type DocumentSummary = components['schemas']['DocumentOut']
export type DocumentDetail = components['schemas']['DocumentDetailOut']
/** No standalone "DocumentType"/"DocumentStatus" schema exists - same
 * derive-from-a-usage-site reasoning as MlTaskType/LifecycleStatus above. */
export type DocumentType = DocumentSummary['document_type']
export type DocumentStatus = DocumentSummary['status']
export type DocumentChunk = components['schemas']['ChunkOut']

export type RagQueryResult = components['schemas']['RagQueryOut']
export type RagQuerySummary = components['schemas']['RagQuerySummaryOut']
export type RagQueryStatus = RagQueryResult['status']
export type RagSource = components['schemas']['SourceOut']

// ---------------------------------------------------------------------------
// Natural-language analytics (Phase 8)
// ---------------------------------------------------------------------------

export type AnalyticsQueryResult = components['schemas']['AnalyticsQueryOut']
export type AnalyticsQuerySummary = components['schemas']['AnalyticsQuerySummaryOut']
export type AnalyticsQueryStatus = AnalyticsQueryResult['status']
/** One result row, keyed by its column name - shape genuinely varies by
 * question (see app/analytics/query_builder.py's result_columns), so
 * there's no fixed schema to name each field. */
export type AnalyticsResultRow = AnalyticsQueryResult['rows'][number]
