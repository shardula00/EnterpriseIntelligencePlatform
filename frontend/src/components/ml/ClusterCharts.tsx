import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ClusterProfile } from '../../api/types'

const CLUSTER_COLORS = ['#2a78d6', '#dc6a5c', '#3fae6a', '#c9982a', '#8a6fd4', '#3fb3b3', '#d46fa8', '#6b7280']

export function ClusterSizeChart({ sizes }: { sizes: Record<string, number> }) {
  const data = Object.entries(sizes).map(([cluster, size]) => ({ cluster: `Cluster ${cluster}`, size }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey="cluster" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} />
        <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} width={48} />
        <Tooltip />
        <Bar dataKey="size" fill="#2a78d6" radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Reshapes [{cluster, feature_means: {income, spend}}] into one row per
 * feature with each cluster as its own bar, so clusters can be compared
 * side-by-side on the same feature - the generic alternative to a 2D
 * scatter plot when there are more than 2 feature columns. */
export function ClusterFeatureMeansChart({ profiles }: { profiles: ClusterProfile[] }) {
  const features = Object.keys(profiles[0]?.feature_means ?? {})
  const data = features.map((feature) => {
    const row: Record<string, string | number> = { feature }
    for (const profile of profiles) {
      row[`Cluster ${profile.cluster}`] = profile.feature_means[feature]
    }
    return row
  })

  return (
    <ResponsiveContainer width="100%" height={Math.max(220, features.length * 50)}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid horizontal={false} stroke="#e2e8f0" />
        <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="feature"
          tick={{ fontSize: 12, fill: '#334155' }}
          axisLine={false}
          tickLine={false}
          width={130}
        />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {profiles.map((profile, i) => (
          <Bar
            key={profile.cluster}
            dataKey={`Cluster ${profile.cluster}`}
            fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]}
            radius={[0, 4, 4, 0]}
            maxBarSize={14}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
