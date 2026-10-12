# NyayaSetu — Grounded Indian Criminal-Law Assistant

> **This file is the project's source of truth.** Read it before every major step. Update it whenever architecture, status, decisions, experiments, or learning progress change.

_Last updated: 2026-10-12 · Phase 0 (Setup) nearly complete_

---

## Project Vision

A legal research assistant for India's new criminal laws: Bharatiya Nyaya Sanhita (BNS), Bharatiya Nagarik Suraksha Sanhita (BNSS) and Bharatiya Sakshya Adhiniyam (BSA). They replaced the IPC, CrPC and Indian Evidence Act on 1 July 2024.

Every answer must be **grounded in the actual statute text, cite exact sections, map old ↔ new section numbers, and refuse when the law doesn't cover the question.**

The engineering thesis we want to prove with measurements:

> *A small, fine-tuned, open-source model with a well-engineered retrieval pipeline can match or beat a large general-purpose model on citation faithfulness, at a fraction of the serving cost.*

## Problem

- The 2024 law change means millions of people (students, lawyers, police, citizens) must relearn section numbers and wording.
- Statutes are written in formal legal language; people ask in everyday English or Hinglish. Keyword search misses the connection.
- General chatbots **hallucinate** section numbers and punishments confidently. In law, a wrong citation is worse than no answer.

## Goals

1. Answer natural-language questions about BNS/BNSS/BSA with **section-level citations**.
2. Map IPC/CrPC/IEA sections ↔ BNS/BNSS/BSA sections reliably, using a lookup tool rather than model memory.
3. **Abstain** ("not covered / I'm not sure") when the retrieved law doesn't support an answer.
4. Measure everything: retrieval quality, citation accuracy, faithfulness, abstention, latency, cost.
5. Run real experiments: no-RAG vs RAG, chunking strategies, dense vs hybrid retrieval, with/without reranking, base vs fine-tuned embeddings, base vs QLoRA-tuned generator, quantization trade-offs.
6. Serve it as a deployed web app with an API, caching, and monitoring.

## Non-goals

- **Not legal advice.** The product shows a clear disclaimer and is positioned as a study/research aid.
- Not covering all Indian law: scope is the three new criminal codes plus their old counterparts. Case law is a stretch goal only.
- Not training an LLM from scratch, which is neither necessary nor feasible.
- Not a polished consumer product: the focus is engineering depth and measured results.

---

## Complete End-to-End Architecture

```text
User (browser)
 ↓
Frontend (chat UI: answer + clickable citations + old↔new mapping panel)
 ↓
API (FastAPI) ── response cache (exact + semantic)
 ↓
Application Layer (request validation, session, logging/tracing)
 ↓
GenAI Pipeline
 ├── 1. Query Understanding
 │     ├── detect explicit section refs ("IPC 420", "Section 302")
 │     ├── query rewriting (casual → legal phrasing)
 │     └── scope check (is this a criminal-law question at all?)
 ├── 2. Tools
 │     └── section_mapper(old_code, section) → new section(s)
 ├── 3. Retrieval
 │     ├── Sparse/keyword search (BM25)
 │     ├── Dense search (embeddings + vector DB)
 │     ├── Fusion (Reciprocal Rank Fusion)
 │     └── Reranking (cross-encoder)
 ├── 4. Context Construction (dedupe, order, token budget, section metadata)
 ├── 5. Generation (LLM → structured JSON: answer, citations[], confidence, abstain flag)
 └── 6. Response Validation
       ├── citation exists? (section IDs checked against the database)
       ├── citation supports claim? (faithfulness check)
       └── fallback to abstention if validation fails
 ↓
Evaluation / Observability (traces, latency, token cost, offline eval suite)
 ↓
Response
```

## Architecture Diagram

```mermaid
flowchart TD
    U[User] --> FE[Frontend]
    FE --> API[FastAPI]
    API <--> C[(Cache)]
    API --> QU[Query Understanding]
    QU --> T[section_mapper tool]
    QU --> R1[BM25 search]
    QU --> R2[Dense vector search]
    R1 --> F[Rank fusion]
    R2 --> F
    F --> RR[Cross-encoder reranker]
    RR --> CC[Context construction]
    T --> CC
    CC --> LLM[LLM: small open model, QLoRA-tuned]
    LLM --> V[Citation + faithfulness validator]
    V --> API
    API --> OBS[Tracing / metrics]
    subgraph Offline
      D[India Code bare acts + mapping tables] --> P[Parser → structured sections]
      P --> IDX[(Vector DB + BM25 index)]
      P --> EV[Eval set]
      EV --> FT[Fine-tuning: embeddings + generator]
    end
    IDX --> R1
    IDX --> R2
```

## Complete User-to-Response Workflow

1. User asks: *"Someone took money from me promising a job and vanished — what's the punishment, and what was the old IPC section?"*
2. API checks the cache. On a miss, it continues.
3. Query understanding: no explicit section number found; rewrites to legal phrasing ("cheating, dishonest inducement to deliver property"); scope check passes.
4. Retrieval: BM25 and dense search each return top-k sections; fusion merges them; the reranker keeps the best ~5.
5. Tool call: the cheating section found in BNS is mapped back to its IPC equivalent via `section_mapper`.
6. Context construction: the selected sections' text, IDs and titles are packed within the token budget.
7. The LLM produces structured JSON: answer text, the citation for each claim, the mapping, and an abstain flag.
8. The validator confirms every cited section exists and supports its claim. If not, it rejects the claim or abstains.
9. The response is returned with clickable citations; the trace (latency, tokens, retrieved IDs) is logged.

---

## Technology Stack

_Tentative. Final choices are recorded in **Architecture Decisions** as we make them._

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Standard for AI work |
| Data parsing | `pypdf` / `pdfplumber`, regex, Pydantic | Turn bare-act PDFs into structured sections |
| Keyword search | BM25 (`rank_bm25` or `bm25s`) | Exact legal terms and section numbers |
| Embeddings | Open model, BGE/E5 family (`sentence-transformers`) | Free, strong, fine-tunable |
| Vector database | Qdrant (local via Docker) | Supports metadata filters and hybrid search; production-grade |
| Reranker | Open cross-encoder (BGE-reranker family) | Big precision gain for a small latency cost |
| Generator LLM | Small open instruct model (Qwen/Llama family, ~3–8B); exact model chosen in Phase 5 | Fine-tunable on free GPUs; cheap to serve |
| Teacher / baseline | One hosted API LLM | Synthetic data generation and comparison baseline |
| Fine-tuning | Hugging Face `transformers` + `peft` (LoRA/QLoRA), `bitsandbytes`; possibly Unsloth | Standard, fits on a free T4 GPU |
| Serving | vLLM (GPU) or llama.cpp / Ollama (CPU, quantized) | Fast, cheap inference |
| API | FastAPI | Async, typed, auto-docs |
| Frontend | Streamlit/Gradio first; maybe React later | Spend effort on AI, not CSS |
| Caching | Redis or in-process (exact + semantic cache) | Latency and cost |
| Observability | Structured logs + Langfuse or OpenTelemetry | Traces per request |
| Experiment tracking | CSV/JSON results + MLflow or Weights & Biases | Reproducible experiments |
| Packaging | Docker + docker-compose | One-command run |
| Compute | Laptop (dev), Google Colab / Kaggle free GPUs (training) | Zero-budget friendly |

## Models

| Role | Model (planned) | What it does |
|---|---|---|
| Embedding | BGE/E5-family, then our fine-tuned version | Turns text into vectors so similar meanings sit close together |
| Reranker | Cross-encoder | Reads query + candidate together and scores relevance precisely |
| Generator | Small open decoder-only transformer, then our QLoRA-tuned version | Writes the cited answer |
| Teacher | Hosted large LLM | Generates synthetic training questions; serves as baseline |
| Judge (eval only) | Hosted LLM + rule checks | Grades faithfulness; calibrated against our own human labels |

**Core architecture to learn deeply:** the decoder-only Transformer, covering tokenization → embeddings → attention → next-token prediction → sampling.

## Data Pipeline

1. **Sources:** BNS, BNSS, BSA, IPC, CrPC and IEA bare acts (India Code, public); official IPC↔BNS / CrPC↔BNSS / IEA↔BSA correspondence tables (exact source to verify in Phase 1).
2. **Parse:** PDF → text → split by Chapter / Section / Sub-section / Explanation / Illustration / Proviso.
3. **Structure:** each unit becomes a record `{act, chapter, section_no, title, text, parts[], old_equivalents[]}`, validated with Pydantic.
4. **Quality checks:** section counts match the official acts; no empty or duplicate sections; spot-check by hand.
5. **Store:** JSONL (source of truth) → BM25 index + Qdrant collection.
6. **Eval data:** a hand-written gold set of 150–300 questions, each labelled with correct section(s) and including out-of-scope and trick questions.

## RAG Pipeline

Query → rewrite → [BM25 ∥ dense] → RRF fusion → cross-encoder rerank → top-k → context builder → LLM → validator.

Chunking strategies to compare: fixed-size tokens · whole section · section with sub-parts split out · parent-child (retrieve small part, send the full section).

## Training/Fine-tuning Pipeline

**A. Embedding fine-tuning**
- Use the teacher LLM to generate realistic user questions for each section, giving (question, section) pairs.
- Train with a contrastive loss (e.g. MultipleNegativesRankingLoss).
- Hold out sections to test generalization.

**B. Generator QLoRA fine-tuning**
- Build training examples: (question + retrieved context) → ideal structured, cited answer, plus abstention examples.
- Answers come from the teacher, then are filtered by the citation validator; keep a human-reviewed subset.
- Train with QLoRA (4-bit base model + LoRA adapters) on a free GPU.
- Compare against the same base model with prompting only.

## Inference Pipeline

- Quantized generator (4-bit/8-bit) served via vLLM or llama.cpp.
- Embedding + reranker models loaded once at startup.
- Exact-match cache plus a semantic cache for similar questions.
- Token-budgeted context; streaming responses.
- Measure p50/p95 latency, tokens/sec, memory, and cost per 1,000 queries.

## Evaluation Strategy

| What | Metric | How |
|---|---|---|
| Retrieval | Recall@k, MRR, nDCG | Against gold section labels |
| Citation accuracy | % cited sections that exist and are correct | Rule check vs database + gold |
| Faithfulness | % claims supported by cited text | LLM judge + human spot-check calibration |
| Answer correctness | Gold-answer agreement | Human + judge on a subset |
| Abstention | Precision/recall on out-of-scope questions | Labelled trick questions |
| Mapping accuracy | % correct old↔new | Against official tables |
| Performance | Latency p50/p95, memory, cost | Benchmark script |

**Rule:** every number in this file comes from an actual run, with the script and config recorded. No invented metrics.

## Deployment Architecture

`docker-compose`: API container + Qdrant + Redis + model server (vLLM on GPU host, or llama.cpp on CPU) + frontend. Target: a free/cheap host for the demo (e.g. Hugging Face Spaces or a small VM). The README documents both "run locally" and "run with a hosted model" modes.

---

## Project Phases

| # | Phase | Key concepts learned |
|---|---|---|
| 0 | Setup: environment, repo, `plan.md` | Project structure, git |
| 1 | Data: collect + parse acts and mapping tables into structured JSONL | Data pipelines, validation |
| 2 | Gold eval set + **no-RAG baseline** (watch LLMs hallucinate) | LLMs, tokens, prompting, hallucination |
| 3 | Dense retrieval: embeddings + Qdrant, RAG v1 | Embeddings, vector search, RAG |
| 4 | Retrieval upgrades: BM25, hybrid, reranking, chunking experiments | Hybrid retrieval, reranking, retrieval eval |
| 5 | Generation: structured cited output, `section_mapper` tool, validator, abstention | Transformers, structured output, tool calling |
| 6 | Evaluation harness: faithfulness, citations, abstention, LLM-as-judge | LLM evaluation |
| 7 | Fine-tune the embedding model | Training, loss, contrastive learning |
| 8 | QLoRA fine-tune the generator | Fine-tuning, LoRA, QLoRA, quantization |
| 9 | Inference optimization: quantization, serving, caching, latency | Inference, serving |
| 10 | API + frontend + observability | Production engineering |
| 11 | Deploy + README + evaluation report + resume material | Communication |

## Concepts I Need to Learn

Each concept is learned when its phase needs it. Status: ⬜ not yet · 🟨 in progress · ✅ understood + implemented

- ⬜ What an LLM is / next-token prediction (Phase 2)
- ⬜ Tokens and tokenization (Phase 2)
- ⬜ Prompting and system prompts (Phase 2)
- ⬜ Hallucination (Phase 2)
- ⬜ Embeddings (Phase 3)
- ⬜ Vector similarity and vector databases (Phase 3)
- ⬜ RAG (Phase 3)
- ⬜ BM25 / keyword search (Phase 4)
- ⬜ Hybrid retrieval + rank fusion (Phase 4)
- ⬜ Reranking / cross-encoders (Phase 4)
- ⬜ Chunking (Phase 4)
- ⬜ Transformers + attention, conceptually (Phase 5)
- ⬜ Context windows and context construction (Phase 5)
- ⬜ Structured outputs (Phase 5)
- ⬜ Tool / function calling (Phase 5)
- ⬜ LLM evaluation, LLM-as-judge (Phase 6)
- ⬜ Training, loss and gradient descent, intuitively (Phase 7)
- ⬜ Fine-tuning (Phase 7)
- ⬜ LoRA (Phase 8)
- ⬜ Quantization + QLoRA (Phase 8)
- ⬜ Inference optimization + serving (Phase 9)
- ⬜ Caching (Phase 9)
- ⬜ APIs, monitoring, deployment (Phases 10–11)

---

## Completed Components

- ✅ Project selection (NyayaSetu chosen over 5 alternatives: best concept coverage with genuine need, public data, measurable hallucination story)
- ✅ `plan.md` created

## Current Component

**Phase 0 — Environment setup and repository skeleton.** 🟨 In progress

Dev machine: Windows + PowerShell, Python 3.12.10 in `.venv` (installed via `py install 3.12` alongside system 3.14), git, GitHub.

- ✅ venv created and verified (`scripts/check_env.py` passes, 2026-10-09)
- ✅ Core files: `.gitignore`, `requirements.txt`, `.env.example`, `README.md`, `scripts/check_env.py`
- ✅ First commit pushed to GitHub: https://github.com/kavyaa005/nyayasetu (2026-10-09)

Repo layout:
```text
nyayasetu/
├── data/raw/            # downloaded PDFs (git-ignored; reproducible via script)
├── data/processed/      # parsed JSONL
├── src/nyayasetu/       # package: ingestion/ retrieval/ generation/ evaluation/ api/
├── notebooks/           # exploration only, never core logic
├── experiments/         # configs + results of each experiment
├── tests/
├── scripts/check_env.py
├── plan.md  README.md  requirements.txt  .gitignore  .env.example
```

## Next Components

1. Phase 0: commit `plan.md` to the repo (last Phase 0 task)
2. Phase 1: Download the six acts + mapping tables; build the parser; produce `data/processed/sections.jsonl`

## Architecture Decisions

| # | Date | Decision | Reason | Alternatives considered |
|---|---|---|---|---|
| ADR-1 | 2026-10-06 | Domain = Indian criminal law (BNS/BNSS/BSA) | Public data, high-stakes hallucination problem, timely, India-relevant | Annual reports, text-to-SQL, schemes, papers, code |
| ADR-2 | 2026-10-06 | Open small model as main generator; API model as teacher/baseline | Makes fine-tuning + serving real; cheap to run | API-only (no fine-tuning learning) |
| ADR-3 | 2026-10-06 | Old↔new mapping via deterministic tool, not model memory | Exact lookups must not be hallucinated | Let LLM recall mappings |
| ADR-4 | 2026-10-06 | Build the eval set **before** RAG | Can't claim improvement without a baseline | Build first, evaluate later |
| ADR-5 | 2026-10-06 | `src/` package layout + per-project venv; raw data git-ignored and re-downloadable by script | Clean imports, reproducible, small repo | Flat scripts; committing PDFs |
| ADR-6 | 2026-10-06 | Python 3.11–3.12 | Best compatibility with ML libraries (PyTorch, bitsandbytes, vLLM) | Newest Python (libraries lag) |

## Experiments

| ID | Question | Phase | Status |
|---|---|---|---|
| E1 | How badly does an LLM hallucinate citations without RAG? | 2 | ⬜ |
| E2 | Chunking: fixed vs section vs parent-child | 4 | ⬜ |
| E3 | Dense vs BM25 vs hybrid | 4 | ⬜ |
| E4 | Reranker on vs off | 4 | ⬜ |
| E5 | Prompt variants for citation format + abstention | 5 | ⬜ |
| E6 | Base vs fine-tuned embeddings | 7 | ⬜ |
| E7 | Base vs QLoRA generator vs large API model | 8 | ⬜ |
| E8 | Quantization: quality vs latency vs memory | 9 | ⬜ |
| E9 | Cache hit rate + latency impact | 9 | ⬜ |

## Results

_No results yet. Only measured numbers go here, each with script name, config and date._

## Known Problems

- Bare-act PDFs may have inconsistent formatting; the parser will need iteration.
- The official correspondence tables may not be one-to-one (some old sections split or merge).
- Free GPU sessions are time-limited, so training must checkpoint.
- LLM-as-judge can be biased; it must be calibrated against human labels.

## Future Improvements

- Case-law retrieval (Supreme Court / High Court judgments)
- Hindi query support
- Amendment tracking / versioned statutes
- Feedback loop: thumbs up/down → new eval data

## Final Resume Material

_Filled in at Phase 11, using only measured results._
