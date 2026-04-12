const BASE = ''

export interface PaperListItem {
  id: string
  title: string
  arxiv_id: string | null
  published_date: string | null
  first_seen_at: string
  score_total: number | null
  tags: string[]
  analysis_basis: string | null
  evidence_level: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface PaperDetail {
  id: string
  title: string
  abstract: string
  arxiv_id: string | null
  authors: string[]
  arxiv_categories: string[]
  published_date: string | null
  first_seen_at: string
  analysis: {
    factual_summary: string
    methodology_inference: string
    innovation_points: string[]
    key_takeaways: string[]
    score_total: number
    score_breakdown: Record<string, number>
    tags: string[]
    evidence_level: string
    evidence_citations: Array<{ claim: string; source: string; page?: number }>
    confidence: number
    analysis_basis: string
  } | null
  sources: Array<{ source_name: string; source_url: string }>
}

export interface ReportListItem {
  id: number
  week_start: string
  week_end: string
  cluster_run_id: number | null
  is_current: boolean
  created_at: string
}

export interface ReportDetail {
  id: number
  week_start: string
  week_end: string
  report_content: string
  highlights: Array<{ title: string; reason: string }>
  created_at: string
}

export async function fetchPapers(params: Record<string, string> = {}): Promise<PaginatedResponse<PaperListItem>> {
  const qs = new URLSearchParams(params).toString()
  const resp = await fetch(`${BASE}/api/papers?${qs}`)
  return resp.json()
}

export async function fetchPaper(id: string): Promise<PaperDetail> {
  const resp = await fetch(`${BASE}/api/papers/${id}`)
  return resp.json()
}

export async function fetchReports(params: Record<string, string> = {}): Promise<PaginatedResponse<ReportListItem>> {
  const qs = new URLSearchParams(params).toString()
  const resp = await fetch(`${BASE}/api/reports?${qs}`)
  return resp.json()
}

export async function fetchReport(id: number): Promise<ReportDetail> {
  const resp = await fetch(`${BASE}/api/reports/${id}`)
  return resp.json()
}

export async function fetchHealth(): Promise<{ status: string; version: string }> {
  const resp = await fetch(`${BASE}/api/health`)
  return resp.json()
}
