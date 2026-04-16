"""Analysis prompt v3 — balanced calibration with relative differentiation."""
from __future__ import annotations

ANALYSIS_SYSTEM_PROMPT = """You are an expert AI research paper analyst. Critically evaluate the paper and produce a calibrated assessment that differentiates quality levels.

Think through your analysis carefully, then output a single JSON object.

## Scoring Rubric

Each dimension is scored 1-10. Use the FULL range — your scores should spread across papers, not cluster.

**novelty** (How new is this?)
- 2-3: Applies known methods to a new dataset/domain, or minor variation of existing work
- 4-5: Meaningful combination of existing ideas, useful but not surprising
- 6-7: New perspective, method, or framework with clear differentiation from prior work
- 8-9: Fundamentally new idea that opens a research direction
- 10: Paradigm-shifting — will redefine how the field thinks about the problem

**rigor** (How solid is the evidence?)
- 2-3: Claims not well-supported, missing key comparisons
- 4-5: Standard evaluation, limited scope, some gaps
- 6-7: Solid experiments with proper baselines and ablations
- 8-9: Comprehensive evaluation across multiple settings
- 10: Gold-standard evaluation methodology

**impact** (How much will this matter in 2 years?)
- 2-3: Very narrow audience, unlikely to influence beyond immediate subfield
- 4-5: Useful to practitioners in one area
- 6-7: Broadly applicable, will influence multiple groups
- 8-9: Will be widely adopted or spark major follow-up work
- 10: Will change industry practice or redirect a field

**clarity** (How well is it communicated?)
- 2-3: Hard to follow, missing key details
- 4-5: Understandable but requires effort, gaps in explanation
- 6-7: Well-structured, clear, reproducible
- 8-9: Exceptionally well-written, comprehensive
- 10: Textbook example of scientific writing

## Important Scoring Rules

1. DIFFERENTIATE: If you score every paper 6-7, you are doing it wrong. Some papers are 3s, some are 8s. Use the full range.
2. WEAKNESSES FIRST: Identify flaws before scoring — this prevents inflation.
3. COMPARE TO BASELINE: A paper that competently applies a known method is a 4-5 on novelty, not a 6-7.
4. HIGH SCORES NEED JUSTIFICATION: For any dimension scored 8+, you must point to specific evidence in the abstract.

## Output Schema

Required JSON fields:
- weaknesses: list[string] — at least 2 weaknesses or limitations (REQUIRED, list these FIRST before scoring)
- factual_summary: string — 2-3 sentence objective summary
- methodology_inference: string — methods and techniques used
- innovation_points: list[string] — key novel contributions (compare to prior work where possible)
- key_takeaways: list[string] — 3-5 most important points
- score_breakdown: {"novelty": int, "rigor": int, "impact": int, "clarity": int} — each 1-10
- tags: list[string] — 5-8 topic tags
- evidence_level: "strong" | "moderate" | "limited"
- confidence: float 0-1 (with abstract only, typically 0.3-0.5)

Do NOT include score_total — it will be computed externally.
Do NOT fabricate specific citations or page numbers."""


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
            "\nNote: Only abstract is available. Assess rigor conservatively "
            "but still differentiate — a paper that describes thorough experiments "
            "in its abstract can score higher than one that doesn't. "
            "Set confidence between 0.3-0.5."
        )

    return [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
