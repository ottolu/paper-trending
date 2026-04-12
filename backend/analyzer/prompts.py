from __future__ import annotations

ANALYSIS_SYSTEM_PROMPT = """You are an expert AI research paper analyst. Analyze the given paper and produce a structured JSON response.

Required JSON fields:
- factual_summary: string — objective summary of what the paper does and finds
- methodology_inference: string — what methods/techniques are used
- innovation_points: list[string] — key novel contributions
- key_takeaways: list[string] — most important points for a researcher
- score_total: float (0-10) — overall significance score
- score_breakdown: object with keys "novelty", "rigor", "impact", "clarity" (each 0-10)
- tags: list[string] — topic tags for categorization
- evidence_level: string — "strong", "moderate", or "limited"
- evidence_citations: list[object] — each with "claim", "source", "page" (if available)
- confidence: float (0-1) — your confidence in this analysis

Output ONLY valid JSON, no markdown fences or explanation."""


def build_analysis_prompt(manifest: dict) -> list[dict]:
    title = manifest["title"]
    abstract = manifest["abstract"]
    authors = ", ".join(manifest.get("authors", []))
    categories = ", ".join(manifest.get("arxiv_categories", []))
    analysis_basis = manifest.get("analysis_basis", "abstract_only")
    chunks = manifest.get("chunks", [])
    sections = manifest.get("sections", [])

    user_parts = [
        f"# Paper: {title}",
        f"Authors: {authors}",
        f"Categories: {categories}",
        f"Analysis basis: {analysis_basis}",
        f"\n## Abstract\n{abstract}",
    ]

    if chunks:
        user_parts.append("\n## Full Text Chunks")
        for chunk in chunks:
            text = chunk["text"] if isinstance(chunk, dict) else chunk
            idx = chunk.get("index", "?") if isinstance(chunk, dict) else "?"
            user_parts.append(f"\n### Chunk {idx}\n{text}")

    if sections:
        section_names = [s.get("title", "") for s in sections if isinstance(s, dict)]
        if section_names:
            user_parts.append(f"\n## Document Sections: {', '.join(section_names)}")

    if analysis_basis == "abstract_only":
        user_parts.append(
            "\nNote: Only abstract is available (abstract_only). "
            "Base analysis solely on abstract. Set confidence accordingly."
        )

    return [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
