import type { MlTaskType } from '../../api/types'

/** Single source of truth for how each of the 4 tasks is labeled/described
 * across the ML section - the routes themselves use the same literal
 * strings the backend does (`MlTaskType`), so there is no separate slug
 * mapping to keep in sync. */
export const TASK_META: Record<
  MlTaskType,
  { label: string; shortLabel: string; description: string }
> = {
  classification: {
    label: 'Binary Classification',
    shortLabel: 'Classification',
    description:
      'Predict a yes/no outcome for each record - e.g. which customers are likely to churn.',
  },
  forecasting: {
    label: 'Time-Series Forecasting',
    shortLabel: 'Forecasting',
    description: 'Project a numeric metric forward in time, using its own chronological history.',
  },
  segmentation: {
    label: 'Customer Segmentation',
    shortLabel: 'Segmentation',
    description: 'Group records into clusters of similar records, based on numeric features.',
  },
  anomaly_detection: {
    label: 'Anomaly Detection',
    shortLabel: 'Anomaly Detection',
    description: 'Flag records that look unusual compared to the rest of the dataset.',
  },
}

export const TASK_TYPES: MlTaskType[] = [
  'classification',
  'forecasting',
  'segmentation',
  'anomaly_detection',
]

export function isMlTaskType(value: string | undefined): value is MlTaskType {
  return TASK_TYPES.includes(value as MlTaskType)
}
