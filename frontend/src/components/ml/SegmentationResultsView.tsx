import type { SegmentationResults } from '../../api/types'
import { isSegmentationPredictions } from '../../api/types'
import { ClusterFeatureMeansChart, ClusterSizeChart } from './ClusterCharts'
import { PredictAction } from './PredictAction'

export function SegmentationResultsView({
  runId,
  results,
}: {
  runId: string
  results: SegmentationResults
}) {
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-wrap gap-3">
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Silhouette score</p>
          <p className="text-lg font-semibold text-slate-900">{results.silhouette_score}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Clusters</p>
          <p className="text-lg font-semibold text-slate-900">{results.n_clusters}</p>
        </div>
      </section>
      <p className="text-xs text-slate-500">
        Silhouette ranges from -1 to 1 - higher means clusters are more clearly separated from each
        other, not just internally tight.
      </p>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Cluster sizes</h2>
        <ClusterSizeChart sizes={results.cluster_sizes} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">
          Feature means by cluster (original units)
        </h2>
        <ClusterFeatureMeansChart profiles={results.cluster_profiles} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Cluster profiles</h2>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Cluster</th>
                <th className="px-3 py-2">Size</th>
                {results.feature_columns.map((column) => (
                  <th key={column} className="px-3 py-2">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {results.cluster_profiles.map((profile) => (
                <tr key={profile.cluster}>
                  <td className="px-3 py-2 font-medium text-slate-800">Cluster {profile.cluster}</td>
                  <td className="px-3 py-2 text-slate-600">{profile.size.toLocaleString()}</td>
                  {results.feature_columns.map((column) => (
                    <td key={column} className="px-3 py-2 text-slate-600">
                      {profile.feature_means[column]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Assign all rows to clusters</h2>
        <PredictAction runId={runId}>
          {(response) =>
            isSegmentationPredictions(response) ? (
              <p className="text-sm text-slate-600">
                Assigned {response.summary.row_count as number} rows to {results.n_clusters} clusters.
              </p>
            ) : null
          }
        </PredictAction>
      </section>
    </div>
  )
}
