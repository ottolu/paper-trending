import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchReports, fetchReport } from '../api'

export default function Reports() {
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: reportList } = useQuery({
    queryKey: ['reports'],
    queryFn: () => fetchReports(),
  })

  const { data: reportDetail } = useQuery({
    queryKey: ['report', selectedId],
    queryFn: () => fetchReport(selectedId!),
    enabled: selectedId !== null,
  })

  return (
    <div className="flex gap-6">
      <div className="w-64 flex-shrink-0">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Reports</h2>
        <ul className="space-y-2">
          {reportList?.items.map((r) => (
            <li key={r.id}>
              <button
                onClick={() => setSelectedId(r.id)}
                className={`w-full text-left px-3 py-2 rounded text-sm ${
                  selectedId === r.id ? 'bg-blue-100 text-blue-800' : 'hover:bg-gray-100 text-gray-700'
                }`}
              >
                {r.week_start} ~ {r.week_end}
              </button>
            </li>
          ))}
          {!reportList?.items.length && (
            <li className="text-sm text-gray-500">No reports yet</li>
          )}
        </ul>
      </div>

      <div className="flex-1">
        {reportDetail ? (
          <div className="bg-white rounded-lg shadow p-6">
            <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: '' }}>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
              {reportDetail.report_content}
            </pre>
          </div>
        ) : (
          <div className="text-gray-500 text-center mt-20">
            Select a report from the left to view
          </div>
        )}
      </div>
    </div>
  )
}
