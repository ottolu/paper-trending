import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchPapers } from '../api'

export default function Papers() {
  const [page, setPage] = useState(1)
  const [scoreMin, setScoreMin] = useState('')
  const [search, setSearch] = useState('')

  const params: Record<string, string> = { page: String(page), page_size: '20' }
  if (scoreMin) params.score_min = scoreMin
  if (search) params.q = search

  const { data, isLoading } = useQuery({
    queryKey: ['papers', params],
    queryFn: () => fetchPapers(params),
  })

  const totalPages = data ? Math.ceil(data.total / 20) : 0

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Papers</h2>

      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Search papers..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          type="number"
          placeholder="Min score"
          value={scoreMin}
          onChange={(e) => { setScoreMin(e.target.value); setPage(1) }}
          className="w-32 rounded-md border border-gray-300 px-3 py-2 text-sm"
          step="0.5"
          min="0"
          max="10"
        />
      </div>

      {isLoading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">HF ♥</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tags</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Basis</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.items.map((paper) => (
                  <tr key={paper.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <Link to={`/papers/${paper.id}`} className="text-blue-600 hover:underline">
                        {paper.title}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`font-bold ${(paper.score_total ?? 0) >= 8 ? 'text-green-600' : 'text-gray-700'}`}>
                        {paper.score_total ?? '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`text-sm ${(paper.hf_likes ?? 0) >= 50 ? 'font-semibold text-pink-600' : 'text-gray-600'}`}>
                        {paper.hf_likes ?? '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {paper.tags.slice(0, 3).map((t) => (
                        <span key={t} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mr-1">
                          {t}
                        </span>
                      ))}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">{paper.analysis_basis}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{paper.first_seen_at?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-500">
              Total: {data?.total ?? 0} papers
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded border text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="px-3 py-1 text-sm">
                Page {page} of {totalPages || 1}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
                className="px-3 py-1 rounded border text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
