# ReqGuard — AI Agents Architecture

## 1. Overview

ReqGuard is a multi-agent system for automated technical requirements validation.

The system consists of four specialized AI agents connected through a sequential processing pipeline.

## 2. AI Agents

### Parser Agent

File: `src/agents/parser.py`

- Extracts requirements from source documents.
- Assigns unique requirement identifiers.
- Preserves original quotes and source locations.
- Validates extracted quotations.
- Supports document chunking.

### Requirement Checker Agent

File: `src/agents/requirement_checker.py`

Detects four categories of individual requirement defects:

- Ambiguity
- Unverifiable requirements
- Incomplete requirements
- Unjustified design decisions

Supports batch processing of up to 10 requirements per LLM request by default.

### Set Checker Agent

File: `src/agents/set_checker.py`

Analyzes relationships between requirements and detects:

- Contradictions
- Gaps
- Duplicates

Validates requirement identifiers and supporting quotations.

### Questioner Agent

File: `src/agents/questioner.py`

- Generates clarification questions.
- Preserves defect identifiers.
- Supports batch processing.
- Provides fallback questions when necessary.

## 3. Processing Pipeline

Document → Parser → Requirement Checker → Set Checker → Questioner → Quote Verification → Report

## 4. API Optimization

Batch processing reduces the number of LLM calls required for individual requirement analysis.

For 29 requirements:

- Sequential processing: 29 calls.
- Batch processing: 3 calls.
- Potential reduction: 89.7%.

These figures exclude other agents and API retries.

## 5. Anti-Hallucination Mechanisms

- Exact source quote validation.
- Requirement ID validation.
- Defect category filtering.
- Duplicate defect removal.
- Final quotation verification.

## 6. Quality Evaluation

The evaluation module calculates:

- True Positives
- False Positives
- False Negatives
- Precision
- Recall
- F1-score

The preliminary manual reference contains eight candidate defects, including five confirmed entries and three requiring further review.

All 17 supporting quotations were verified against the source document.

## 7. Automated Testing

| Component | Passed tests |
|---|---:|
| Parser | 6 |
| Requirement Checker | 8 |
| Set Checker | 10 |
| Questioner | 10 |
| Batch Processing | 12 |
| Evaluation Metrics | 15 |
| Total | 61 |

All 61 automated tests passed.

## 8. Current Limitations

- Real LLM validation remains pending due to Gemini API quota restrictions.
- Dry-run results do not represent actual AI detection quality.
- The manual reference is preliminary and requires independent review.
- Final Precision, Recall and F1-score have not yet been established.