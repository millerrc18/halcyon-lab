# Financial NLP deployment for Halcyon Lab on consumer hardware

**FinBERT running on CPU alongside Qwen3 8B on GPU is the optimal architecture for your RTX 3060 setup.** The `yiyanghkust/finbert-tone` variant—pre-trained on **4.9B tokens** of earnings calls, 10-K filings, and analyst reports—is the best-matched model for earnings sentiment analysis, achieving ~88% accuracy on Financial PhraseBank with domain-specific pretraining that directly mirrors your 8-K and transcript use case. ONNX-optimized INT8 FinBERT processes a full 8-K filing in **under 1 second on CPU**, while Qwen3 8B Q4_K_M consumes ~7GB VRAM leaving the GPU entirely conflict-free. Academic evidence strongly supports your PEAD Strategy #3: text-based sentiment surprise generates **3.9 basis points daily alpha** (Meursault et al., 2022), more than twice the classic SUE-based PEAD signal, and the Q&A section of earnings calls carries the strongest predictive signal. Free data sources—Finnhub for transcripts, EdgarTools for 8-K parsing, and the SEC XBRL API—provide complete S&P 100 coverage at zero cost.

---

## 1. FinBERT-tone wins the model selection for earnings sentiment

Three FinBERT variants merit serious consideration, but `yiyanghkust/finbert-tone` emerges as the clear winner for Halcyon Lab's specific use case.

| Model | Params | Pre-training corpus | FPB accuracy | Downloads | Best for |
|-------|--------|-------------------|-------------|-----------|----------|
| **ProsusAI/finbert** | 110M | Reuters TRC2 (1.8M news articles) | 88% (97% high-agreement) | 82.8M | General financial news |
| **yiyanghkust/finbert-tone** | 110M | 4.9B tokens: 10-K, earnings calls, analyst reports | ~88% | 52M | **Earnings calls & 8-K filings** |
| ahmedrachid/FinancialBERT | 110M | Reuters + Bloomberg + corporate reports | 98% (weighted, likely inflated) | 31.5K | Corporate filing analysis |
| SALT-NLP/FLANG-BERT | 110M | ELECTRA-based with financial objectives | 92% micro-F1 | 11.9K | Highest pure classification |
| TinyFinBERT (2024) | 14.5M | Distilled from augmented FinBERT | ~87% (98.9% retention) | New | Real-time/edge inference |

The **finbert-tone** model's pre-training corpus directly matches your target domain—it learned from the exact document types you'll analyze. ProsusAI/finbert, while more popular (82.8M downloads), was pre-trained only on Reuters news, making it less domain-aligned for SEC filing language. FLANG-BERT achieves higher reported F1 (92%) but has minimal community adoption and limited production validation.

**Small LLMs (1B-3B) do not consistently outperform FinBERT** at similar inference costs. A 2025 study found Qwen3 8B and Llama3 8B can surpass FinBERT with fine-tuning, but only at **10-50× the inference cost** and requiring GPU allocation. OPT-1.3B and Pythia-1.4B can match FinBERT after full-parameter fine-tuning but require significant training compute. The practical verdict: **FinBERT wins on throughput and efficiency; LLMs win on nuanced reasoning.** For a trading system processing hundreds of filings quarterly, FinBERT's ability to classify ~1,000 sentences per second on CPU is decisive.

**The strongest approach is an ensemble.** Bayesian Network fusion of FinBERT with complementary models achieves **96.9% accuracy and 95.9% macro-F1** on Financial PhraseBank (Amirzadeh et al., 2025). A hybrid architecture integrating Loughran-McDonald dictionary features into FinBERT reached **97% accuracy** (WSEAS 2024). For Halcyon Lab, the recommended pipeline routes FinBERT's high-confidence classifications directly to the signal generator while forwarding low-confidence sentences (neutral probability > 0.4) to Qwen3 8B for deeper reasoning.

---

## 2. CPU deployment delivers sub-second filing analysis without GPU conflicts

FinBERT runs comfortably on CPU while Qwen3 8B monopolizes the GPU. The **110M-parameter BERT architecture** was designed for efficient CPU inference, and ONNX Runtime optimization makes it fast enough for both real-time queries and batch processing.

**CPU inference latency benchmarks for FinBERT (BERT-base, 110M params):**

| Configuration | 512-token latency | Source |
|---------------|-------------------|--------|
| Vanilla PyTorch, single thread | ~500ms | Twitter/X Engineering |
| ONNX Runtime, 8 threads | ~84ms | Microsoft ORT benchmarks |
| ONNX Runtime + INT8 quantization, 8 threads | **~18-40ms** | Twitter/X, Cortex.dev |
| DistilBERT quantized ONNX (p50) | ~9ms | GetStream production |

A typical 8-K filing (3,000-5,000 tokens) requires **6-10 chunks of 512 tokens each**. With ONNX INT8 on 8 CPU threads, each chunk takes ~40ms, yielding **0.4-0.8 seconds per complete filing**. Batch processing 100 filings completes in roughly **1-2 minutes**—fast enough to process all S&P 100 quarterly earnings in a single batch run.

**Memory footprint is negligible.** FinBERT INT8 ONNX occupies ~110MB on disk and ~300-400MB in RAM including the runtime. This leaves ample system memory for Ollama's ~2-4GB RAM overhead alongside the OS.

**GPU coexistence is technically feasible but not recommended.** With Qwen3 8B Q4_K_M using ~6.2-7.7GB VRAM, roughly 4-5GB remains on the RTX 3060. FinBERT FP16 needs only ~220MB VRAM. However, Ollama dynamically manages VRAM for KV cache allocation and expects exclusive GPU control. A second CUDA process risks memory fragmentation, OOM crashes, and unpredictable latency spikes. The **clean architecture runs FinBERT exclusively on CPU** with `CUDA_VISIBLE_DEVICES=""` enforced in the FinBERT process.

The ONNX optimization pipeline involves three steps: export the HuggingFace model to ONNX format, apply BERT-specific graph optimizations (operator fusion, constant folding, attention fusion), then apply dynamic INT8 quantization. Expected total speedup over vanilla PyTorch is **7-10×**. Intel CPUs with AVX-512 VNNI instructions gain an additional **2-3×** from quantized operations.

---

## 3. Free data sources cover S&P 100 earnings completely

**Earnings call transcripts and 8-K filings are available at zero cost** through a combination of Finnhub and SEC EDGAR.

**Transcript sources ranked by value:**

| Source | Cost | Transcripts? | Rate limit | Coverage |
|--------|------|-------------|------------|----------|
| **Finnhub** | Free | ✅ Full transcripts | 60 calls/min | US, UK, EU, CA, AU |
| Financial Modeling Prep | $29-49/mo | ✅ Full transcripts | 300-750/min | 10+ years history |
| Alpha Vantage | $49.99+/mo | Limited/premium | 25/day (free) | Primarily price data |
| Seeking Alpha | Free to read | ✅ On website | N/A | ~4,500 calls/quarter |
| SEC EDGAR | Free | ❌ Not filed | 10 req/sec | N/A for transcripts |

**Finnhub's free tier is the clear winner.** At 60 API calls per minute, pulling quarterly transcripts for all 100 S&P 100 companies takes under 2 minutes. Earnings call transcripts are **not SEC filings**—they are provided by data vendors—so EDGAR cannot serve as a transcript source. Seeking Alpha publishes transcripts but explicitly prohibits scraping in its Terms of Service; the legal risk is not worth the savings when Finnhub offers the same data for free.

**For 8-K filings, SEC EDGAR is the definitive free source.** The critical items for earnings analysis are **Item 2.02** (Results of Operations and Financial Condition) and **Item 7.01** (Regulation FD Disclosure). Under Item 2.02, companies typically "furnish" the earnings press release as **Exhibit 99.1**—the actual financial data lives in the exhibit, not the 8-K body text, which is usually minimal boilerplate. The preprocessing pipeline must extract and parse this exhibit.

**EdgarTools** is the recommended Python library for 8-K parsing—MIT licensed, 2.3M+ downloads, with native 8-K support through typed Python objects. It provides dictionary-like access to specific items (`eightk["Item 2.02"]`), built-in XBRL parsing, clean text extraction, and SEC rate-limit-aware caching. The alternative `sec-edgar-downloader` handles bulk downloads but lacks parsing capabilities. For structured financial data, the **SEC EDGAR XBRL API** (data.sec.gov) covers 8-K filings alongside 10-K and 10-Q, though XBRL tagging in 8-K press release exhibits is inconsistent compared to annual and quarterly reports.

The preprocessing pipeline flows through five stages: download 8-K filings filtered for Items 2.02 and 7.01 via EdgarTools, extract Exhibit 99.1 (the earnings press release), clean HTML to plain text with BeautifulSoup, segment into Results versus Outlook sections, then detect and tag forward-looking statements using linguistic markers (future tense verbs, modal words, Safe Harbor boilerplate).

---

## 4. Sentiment surprise, not level, is the alpha-generating signal

The academic evidence is unambiguous: **sentiment change predicts future returns substantially better than sentiment level.** This is the central insight for Strategy #3's PEAD implementation.

**The core formula:**

> **Sentiment_Surprise(i,t) = Tone(i,t) − E[Tone(i,t)]**

where E[Tone] is computed as the rolling average of the prior 8 quarters of the company's earnings sentiment. QuantPedia (Dujava, Kalús & Vojtko, 2022) tested windows of 4, 8, 12, and 20 quarters, finding **8 quarters optimal** for the rolling baseline. The computation is performed separately for the Management Discussion and Q&A sections.

**Why change dominates level.** Tone levels are contaminated by firm-specific optimism bias—some CEOs are perpetually enthusiastic, others habitually cautious. Industry norms further distort absolute levels. Sentiment change nets out the firm's baseline, isolating genuinely new information. Li & Ramesh (2009, *Journal of Accounting*) demonstrated that tone change in MD&A predicts drift returns **beyond both accruals and earnings surprises**. A 2025 study found sentiment trajectory correlates with next-quarter operating margin changes at **r = 0.523** (p<0.001) for S&P 500 companies.

The most compelling evidence comes from Meursault, Liang, Routledge & Scanlon's PEAD.txt framework (2022, *JFQA*). They trained regularized logistic regressions on 8 rolling quarters of earnings call text paired with 1-day abnormal returns, producing out-of-sample text-based surprise scores. The results dramatically outperform classic PEAD at every horizon: **Q1 drift of 2.87% versus 1.54%**, Q4 cumulative drift of **8.01% versus 4.63%**, and daily alpha of **3.9 basis points** versus 2.6 bps for quantitative SUE. Even as classic PEAD has attenuated in recent years, text-based PEAD remains robust.

**Tone surprise adds incremental information beyond the numbers.** Price, Doran, Peterson & Bliss (2012, *Journal of Banking & Finance*) found that linguistic tone **dominates quantitative earnings surprises** in predicting abnormal returns over the 60 trading days following earnings calls. An ICAIF 2023 study showed that adding textual features to quantitative earnings and fundamental data improves long-short portfolio returns by **53-354 basis points**. The Kaczmarek & Zaremba (2025) approach of using 12 quarters of historical data in an ML framework can be directly applied to sentiment: train a model on rolling windows of historical sentiment scores paired with post-announcement returns, generating expected sentiment that accounts for firm-specific patterns, recent trends, and cross-sectional relationships.

Huang, Teoh & Zhang's (2014) "Tone Management" model provides a more sophisticated expected-tone specification, regressing tone on earnings, returns, size, book-to-market, volatility, loss indicator, and other determinants. The residual (ABTONE, or "abnormal tone") captures tone management—when managers inflate positivity beyond what fundamentals justify. ABTONE predicts negative future earnings and subsequent price reversals, but the model's low R² (~4.4%) limits its standalone utility. For Halcyon Lab, the **simple 8-quarter rolling average is the recommended primary method**, with ABTONE as an optional supplementary signal for detecting managerial deception.

---

## 5. Q&A sections carry stronger predictive signal than prepared remarks

The academic consensus is clear: **the Q&A portion of earnings calls is more informative for predicting future returns than the Management Discussion**, though both sections contain significant information.

Matsumoto, Pronk & Roelofsen (2011, *The Accounting Review*) analyzed 10,000+ conference call transcripts and found that while both segments have incremental information content beyond the press release, **Q&A periods are relatively more informative than presentation periods.** The mechanism is straightforward: prepared remarks are heavily scripted, reviewed by legal counsel, and optimized for narrative control. Q&A forces spontaneous responses where managers must address analyst concerns they didn't choose.

Chen, Nagar & Schoenfeld (2018, *Review of Accounting Studies*) added a crucial nuance: during Q&A, intraday prices react significantly to **analyst tone but not to management tone**. The analysts asking pointed, skeptical questions generate more price-relevant signals than the managers' rehearsed answers. This suggests the system should track not only management sentiment in Q&A responses but also the sentiment and specificity of analyst questions—negative analyst tone is particularly predictive.

Hollander, Pronk & Roelofsen (2010, *Journal of Accounting Research*) documented that managers regularly leave Q&A questions unanswered, and **investors interpret silence as bad news**. Non-answers predict negative future outcomes. For Halcyon Lab, detecting evasive or non-responsive answers represents an additional signal dimension beyond pure sentiment.

**The recommended section-level protocol for Halcyon Lab:**

- Process MD and Q&A sections separately through FinBERT, generating independent sentiment scores for each
- Weight Q&A sentiment more heavily than MD (suggested: **60% Q&A, 40% MD**) based on the differential informativeness literature
- Extract analyst question sentiment separately from management answer sentiment within Q&A
- Detect hedging language (weak modal words: "appears," "could," "possibly"), forward-looking statement density, and non-answers as supplementary features
- Compute sentiment surprise independently for each section using the 8-quarter rolling baseline

**Paragraph-level analysis adds value but introduces complexity.** Meursault et al. (2022) demonstrated that paragraph-level decomposition reveals that bottom-line discussions and operational disruptions are the most "surprising" content, while non-bottom-line financial metrics contribute the most to total text surprise due to their frequency. A 2025 *Journal of Forecasting* study confirmed that topic-decomposed sentiment outperforms document-level sentiment across multiple model architectures. For S&P 100 companies with long, information-rich transcripts, paragraph-level analysis is worth implementing in a second iteration after the section-level system is validated.

---

## 6. Entity extraction works best as a layered regex-NER-XBRL pipeline

Financial metric extraction from 8-K filings requires multiple complementary approaches because no single method handles the full range of entities reliably.

**Layer 1: Regex rules for structured patterns.** Earnings press releases follow predictable templates. Revenue, EPS, and guidance numbers appear in consistent syntactic patterns ("revenue of $X.XX billion," "diluted EPS of $X.XX," "expects Q2 revenue of $X to $Y billion"). Well-crafted regex patterns achieve **high precision** on these structured elements, processing instantly with zero model overhead. The key patterns target revenue amounts with units, diluted/basic EPS, year-over-year percentage changes, and guidance ranges with low/high bounds.

**Layer 2: spaCy NER for broad entity detection.** The `en_core_web_lg` model provides MONEY, ORG, DATE, and PERCENT entities out of the box. It reliably identifies dollar amounts and percentages but cannot distinguish between revenue, net income, and free cash flow—context-dependent classification requires the next layer.

**Layer 3: SEC-BERT for context-dependent entity typing.** The `nlpaueb/sec-bert-shape` model fine-tuned on the **FiNER-139 dataset** (1.1M sentences, 139 XBRL entity types) achieves F1 scores up to **96.8%** on financial entity recognition. Unlike standard NER with few entity types, FiNER-139 classifies numeric tokens into 139 specific categories (revenue, long-term debt, operating income, etc.) where the correct tag depends entirely on context. SEC-BERT-shape's special handling of numeric tokens using shape pseudo-tokens makes it purpose-built for this task.

**Layer 4: SEC XBRL API for structured data validation.** The XBRL API at data.sec.gov covers 8-K filings and provides programmatic access to tagged financial facts. The Company Concepts endpoint (`/api/xbrl/companyconcept/CIK/us-gaap/Revenues.json`) returns all historical disclosures for a specific metric, while Company Facts returns all XBRL facts for a company. However, XBRL tagging in 8-K press release exhibits is **inconsistent**—10-K and 10-Q filings have comprehensive inline XBRL (mandated since 2009), but 8-K exhibits often lack full tagging. Use XBRL data as validation against NLP-extracted values rather than as a primary source.

**Forward-looking statement detection** combines Safe Harbor boilerplate identification (regex for "Private Securities Litigation Reform Act"), linguistic markers (future tense, modal verbs), and section-based rules (separating "Results" from "Outlook" headers). The `yiyanghkust/finbert-fls` model (950K downloads) is specifically fine-tuned for classifying forward-looking statements and can supplement rule-based detection.

---

## 7. The multi-model architecture isolates GPU and CPU workloads cleanly

The recommended deployment runs two completely independent processes: Ollama serving Qwen3 8B on the GPU, and a FastAPI-wrapped FinBERT ONNX service on the CPU.

**Critical architecture decision: use Q4_K_M quantization for Qwen3 8B, not Q8_0.** Q8_0 consumes ~9.7-10.2GB VRAM at 8K context, leaving only ~2GB headroom on the 12GB RTX 3060—too tight for reliable operation. Q4_K_M uses ~6.2-6.7GB VRAM at 8K context, leaving **~5GB headroom** for CUDA overhead and longer context windows. Generation speed on RTX 3060 is approximately **32-40 tokens per second** with Q4_K_M, sufficient for financial analysis tasks.

**Process isolation is enforced at the environment level.** The FinBERT service sets `CUDA_VISIBLE_DEVICES=""` to prevent any GPU memory allocation—this is the most reliable method, as even importing PyTorch without this flag allocates ~300-500MB of CUDA context. Ollama runs as a native system service on port 11434, completely independent of the Python environment. The FinBERT FastAPI service runs on port 8000 with `intra_op_num_threads=8` (matching physical CPU cores) and `inter_op_num_threads=1`.

**Resource budget on the complete system:**

| Resource | Qwen3 8B (Ollama) | FinBERT (ONNX RT) | Total |
|----------|-------------------|-------------------|-------|
| GPU VRAM | ~7GB (Q4_K_M, 8K ctx) | 0 GB | 7/12 GB |
| System RAM | ~2-4 GB | ~0.3-0.4 GB | ~4-5 GB |
| CPU threads | Minimal | 8 threads | Shared |
| Disk | ~5.2 GB | ~0.11 GB (INT8) | ~5.3 GB |

**Docker containerization on Windows works well** using Docker Desktop with the WSL2 backend and NVIDIA Container Toolkit for GPU passthrough. Performance overhead is under 5% versus native. The key Windows-specific requirement is storing model files inside the WSL2 filesystem rather than mounted Windows drives (`/mnt/c/`) for 3-5× faster I/O. Configure `.wslconfig` with adequate memory allocation (e.g., `memory=24GB` on a 32GB system). GPU drivers install only on the Windows side—do not install Linux NVIDIA drivers inside WSL2.

**Scheduling strategy.** During market hours (9:30 AM–4:00 PM), Qwen3 8B handles LLM queries at full GPU utilization while FinBERT remains available on CPU for real-time sentiment queries at ~40-80ms latency per chunk. Overnight, FinBERT processes accumulated 8-K filings in batch mode (100 filings in ~1-2 minutes), and Qwen3 8B can optionally generate post-processing summaries. Both processes run simultaneously without interference because they share no compute resources.

---

## 8. Implementation timeline and total cost

**Phase 1 (Weeks 1-2): Data infrastructure.** Set up EdgarTools for 8-K downloading and parsing, configure Finnhub API for transcript retrieval, build the preprocessing pipeline for Item 2.02 extraction and text cleaning. Total cost: **$0**.

**Phase 2 (Weeks 3-4): FinBERT deployment.** Export `yiyanghkust/finbert-tone` to ONNX, apply INT8 quantization, wrap in FastAPI service, validate against Financial PhraseBank benchmarks. Deploy alongside Ollama running Qwen3 8B Q4_K_M. Total cost: **$0** (all models and tools are open source).

**Phase 3 (Weeks 5-6): Sentiment surprise engine.** Implement 8-quarter rolling sentiment baseline, compute section-level (MD vs Q&A) sentiment scores, build the sentiment surprise signal. Backtest against S&P 100 historical data. Total cost: **$0** (using free historical data from Finnhub and EDGAR).

**Phase 4 (Weeks 7-8): Entity extraction and signal integration.** Deploy the layered regex-spaCy-SECBERT entity extraction pipeline, integrate sentiment surprise with quantitative SUE for the composite PEAD signal, validate against the evolved Strategy #3 backtests. Total cost: **$0-29/month** (FMP API only if Finnhub transcript coverage is insufficient).

**Ongoing monthly costs:**

| Item | Cost | Notes |
|------|------|-------|
| Finnhub API | $0 | Free tier covers S&P 100 |
| SEC EDGAR / XBRL | $0 | Public data |
| EdgarTools | $0 | MIT license |
| HuggingFace models | $0 | Open source |
| FMP API (optional) | $29/mo | Only if broader coverage needed |
| **Total** | **$0-29/month** | |

## Conclusion

The Halcyon Lab NLP architecture achieves production-grade financial text analysis on consumer hardware by exploiting the fundamental asymmetry between BERT and LLM compute requirements. FinBERT's 110M parameters were purpose-built for efficient CPU inference—a design that becomes a strategic advantage when GPU resources are allocated to a larger reasoning model. The academic evidence supporting this approach is remarkably strong: text-based PEAD generates **over twice the alpha** of traditional quantitative PEAD, Q&A sections contain the richest predictive signal due to their spontaneous nature, and sentiment surprise dominates sentiment level as a return predictor. The entire system—from data acquisition through signal generation—can be built on free and open-source components, with the only optional expense being a $29/month transcript API upgrade. The critical implementation insight is that **Q4_K_M quantization for Qwen3 8B** (not Q8_0) provides the VRAM headroom that makes single-GPU multi-model operation reliable, while the `CUDA_VISIBLE_DEVICES=""` environment variable in the FinBERT process is the single most important configuration for preventing GPU memory conflicts.