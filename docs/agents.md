# ReqGuard — AI Agents Architecture

## 1. Overview

ReqGuard is a multi-agent system for automated validation of technical requirements.

Four LLM agents and three code-only components are connected in a sequential pipeline.
Two LLM providers are used: Google Gemini and Groq. If one is unavailable, the other takes over.

## 2. Processing Pipeline

```text
Document → Reader → Parser → Requirement Checker ─┐
                          └→ Set Checker ─────────┴→ Duplicate Checker → Questioner → Verifier → Report
```

| Step | Component | Type | Model |
|---|---|---|---|
| 1 | Reader (`src/pdf_reader.py`) | code | — |
| 2 | Parser Agent | LLM + code | Gemini |
| 3 | Requirement Checker Agent | LLM | Gemini |
| 4 | Set Checker Agent | LLM | Groq `gpt-oss-120b` (reasoning model) |
| 5 | Duplicate Checker | code | — |
| 6 | Questioner Agent | LLM | Gemini |
| 7 | Verifier (`src/verifier.py`) | code | — |
| 8 | Report (`src/report.py`) | code | — |

## 3. Components

### Reader

File: `src/pdf_reader.py`

- Reads `.pdf`, `.md` and `.txt`.
- Keeps line numbers for MD/TXT and page numbers for PDF.
- Repairs typical PDF extraction artifacts (hyphenation, broken lines).

### Parser Agent

File: `src/agents/parser.py`

- Extracts requirements with a verbatim quote and source location; temperature 0.
- Splits long documents into chunks (~3,500 characters) at section headings.
- Ignores diagrams in code blocks (BPMN, sequence): they illustrate, not specify.
- Re-parses sections where most lines were left without requirements (up to 4 extra requests).
- Parses acceptance criteria tables with code, row by row.
- Drops template service sections (requirements review checklist, approvers, task passport).

### Requirement Checker Agent

File: `src/agents/requirement_checker.py`

Checks each requirement against ISO/IEC/IEEE 29148:2018 and IEEE 830-1998 and detects:

- Ambiguity
- Unverifiable requirements
- Incomplete requirements
- Unjustified design decisions

Processes up to 10 requirements per LLM request.

### Set Checker Agent

File: `src/agents/set_checker.py`

Analyzes the requirement set as a whole in two passes — business rules and API consistency — and detects:

- Contradictions
- Gaps
- Duplicates

- Receives the full document with line numbers, so quotes may come from any part of it
  (tables, JSON examples, status lists).
- Rejects non-existent requirement IDs and quotes that are not in the document.
- Runs on a reasoning model (Groq); if the request does not fit the Groq limit, it goes to the next model in the chain.

### Duplicate Checker

File: `src/agents/duplicate_checker.py` (code only)

- Merges the same problem reported by different agents or for different requirements.
- Two defects are merged when their quotes overlap or share a key phrase,
  and their explanations are similar.
- The merged defect keeps all quotes and related requirement IDs.

### Questioner Agent

File: `src/agents/questioner.py`

- Generates one clarification question per defect for the document author.
- Processes up to 15 defects per request.
- Preserves defect identifiers.
- Uses a template question if the model does not answer.

### Verifier

File: `src/verifier.py` (code only)

- Checks every quote against the source document.
- Drops defects whose quote is not found.
- Computes the line number itself; for short repeated quotes it picks the occurrence
  closest to the related requirement.

### LLM wrapper

File: `src/llm.py`

- One interface for Gemini and Groq; models without an API key are skipped.
- Default chain: `gemini-2.5-flash-lite` → `gemini-3.5-flash-lite` → `gemini-3.6-flash` → `groq:openai/gpt-oss-120b`.
- Handles free-tier limits: per-minute limit (wait and retry), daily limit and unavailable model (skip for the rest of the run),
  overload (switch model), request too large (next model).
- Caches answers on disk (`.llm_cache/`).
- Records which models actually answered; the list goes to the report passport.

## 4. API Usage

Batching reduces the number of LLM calls. For the case document (`docs/requirements.md`, 46 requirements),
one full run takes about 12–15 requests:

| Step | Requests |
|---|---:|
| Parser | 3–5 |
| Requirement Checker | 5 |
| Set Checker | 2 |
| Questioner | 2–3 |

Without batching, the requirement check alone would take 46 requests.

## 5. Anti-Hallucination Mechanisms

- Verbatim quotes are required; matching tolerates only separators (spaces, table pipes) and `ё/е`,
  and the report always contains the exact document text.
- Line numbers are computed by code, not by the model.
- Requirement IDs are validated.
- Defect types are filtered to the allowed categories.
- Duplicate defects are merged.
- Final quote verification before the report.
- Temperature 0 for the parser and the set checker.

## 6. Quality Evaluation

The evaluation module (`evaluation/evaluate.py`) calculates True Positives, False Positives,
False Negatives, Precision, Recall and F1-score against a reference markup
(`evaluation/ground_truth.json`).

On the case document, manual comparison with 15 reference defects gives
Recall 40–47% and Precision about 30% (range across runs).

## 7. Automated Testing

| Component | Tests |
|---|---:|
| Parser | 8 |
| Requirement Checker | 8 |
| Batch Processing | 12 |
| Set Checker | 10 |
| Duplicate Checker | 4 |
| Questioner | 10 |
| LLM wrapper | 14 |
| Evaluation Metrics | 15 |
| Total | 81 |

Tests run without network or API keys: models are replaced with stubs.

```bash
python -m pytest -q
```

## 8. Current Limitations

- Finds about half of the reference defects; multi-step contradictions are found less often than ambiguity.
- Some findings are minor (UI details, error message texts).
- Free-tier limits: Gemini allows about 20 requests per day per model and is sometimes overloaded;
  Groq allows 8,000 tokens per minute.
- For PDF the location is a page, not a line; tables from PDF lose their structure.
