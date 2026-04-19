import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchPaper } from '../api'

export default function PaperDetail() {
  const { paperId } = useParams<{ paperId: string }>()
  const { data: paper, isLoading, error } = useQuery({
    queryKey: ['paper', paperId],
    queryFn: () => fetchPaper(paperId!),
    enabled: !!paperId,
  })

  if (isLoading) return <p className="text-gray-500">Loading...</p>
  if (error || !paper) return <p className="text-red-500">Paper not found</p>

  const a = paper.analysis

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">{paper.title}</h2>
        <p className="text-sm text-gray-500 mt-1">
          {paper.authors?.join(', ')} | {paper.published_date || 'Unknown date'}
        </p>
        <div className="flex flex-wrap gap-2 mt-2 items-center">
          {paper.arxiv_id && (
            <a href={`https://arxiv.org/abs/${paper.arxiv_id}`} target="_blank" rel="noopener noreferrer"
               className="text-sm text-blue-600 hover:underline">
              arXiv: {paper.arxiv_id}
            </a>
          )}
          {paper.sources?.map((s) => (
            <a key={s.source_url} href={s.source_url} target="_blank" rel="noopener noreferrer"
               className="text-sm text-blue-600 hover:underline">
              {s.source_name}
            </a>
          ))}
          {paper.hf_likes != null && (
            <span className="inline-flex items-center gap-1 text-sm font-medium text-pink-600">
              <span>♥</span>
              <span>{paper.hf_likes} on HuggingFace</span>
            </span>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-2">Abstract</h3>
        <p className="text-gray-700">{paper.abstract}</p>
      </div>

      {a && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <p className="text-sm text-gray-500">Score</p>
              <p className={`text-3xl font-bold ${a.score_total >= 8 ? 'text-green-600' : 'text-gray-700'}`}>
                {a.score_total}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <p className="text-sm text-gray-500">Evidence</p>
              <p className="text-xl font-semibold text-gray-700">{a.evidence_level}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <p className="text-sm text-gray-500">Confidence</p>
              <p className="text-xl font-semibold text-gray-700">{(a.confidence * 100).toFixed(0)}%</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <p className="text-sm text-gray-500">Basis</p>
              <p className="text-xl font-semibold text-gray-700">{a.analysis_basis}</p>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-2">事实摘要</h3>
            <p className="text-gray-700">{a.factual_summary}</p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-2">方法推断</h3>
            <p className="text-gray-700">{a.methodology_inference}</p>
          </div>

          {a.innovation_points?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-2">创新点</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-700">
                {a.innovation_points.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          )}

          {a.key_takeaways?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-2">关键结论</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-700">
                {a.key_takeaways.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {a.tags?.map((tag) => (
              <span key={tag} className="px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800">
                {tag}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
