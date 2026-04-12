import { useQuery } from '@tanstack/react-query'
import { fetchPapers, fetchHealth } from '../api'

export default function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth })
  const recentPapers = useQuery({
    queryKey: ['papers', 'recent'],
    queryFn: () => fetchPapers({ page_size: '10', sort: 'updated_at_desc' }),
  })

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">System Status</h3>
          <p className="mt-2 text-3xl font-bold text-green-600">
            {health.data?.status === 'ok' ? 'Online' : 'Loading...'}
          </p>
          <p className="text-sm text-gray-500">v{health.data?.version}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Total Papers</h3>
          <p className="mt-2 text-3xl font-bold text-gray-900">
            {recentPapers.data?.total ?? '—'}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">High Score (≥8.0)</h3>
          <p className="mt-2 text-3xl font-bold text-blue-600">
            {recentPapers.data?.items.filter((p) => (p.score_total ?? 0) >= 8.0).length ?? '—'}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Recent Papers</h3>
        </div>
        <ul className="divide-y divide-gray-200">
          {recentPapers.data?.items.map((paper) => (
            <li key={paper.id} className="px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <a href={`/papers/${paper.id}`} className="text-blue-600 hover:underline font-medium">
                    {paper.title}
                  </a>
                  <div className="text-sm text-gray-500 mt-1">
                    {paper.tags.map((t) => (
                      <span key={t} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mr-1">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-lg font-bold ${(paper.score_total ?? 0) >= 8 ? 'text-green-600' : 'text-gray-600'}`}>
                    {paper.score_total ?? '—'}
                  </span>
                  <p className="text-xs text-gray-400">{paper.first_seen_at?.slice(0, 10)}</p>
                </div>
              </div>
            </li>
          ))}
          {recentPapers.isLoading && <li className="px-6 py-4 text-gray-500">Loading...</li>}
        </ul>
      </div>
    </div>
  )
}
