# Week 5 Lab — Submission

**Student:** Mingjing Zhang
**Course:** CSE552 — Full Stack Software Development in the Age of AI Agents
**Lab:** Week 5 — AI-Powered Book Assistant ("Adding Intelligence to Your App")
**Date:** 2026-05-31

---

## 1. GitHub Repositories

| Repo | URL |
|---|---|
| **Backend** (FastAPI + PostgreSQL + Anthropic SDK) | https://github.com/mingjing-zhang/week-05-api |
| **Frontend** (Next.js 16 + Tailwind, chat UI) | https://github.com/mingjing-zhang/week-05-frontend |

Both repos are **public**. The `ANTHROPIC_API_KEY` in `.env` and the `NEXT_PUBLIC_API_URL` in `.env.local` are excluded from version control via `.gitignore` — **no secrets in the committed history**, verified via the GitHub UI.

Both repos start fresh from Week 4 and add the AI layer on top, following the per-week-portfolio convention.

---

## 2. How to run the whole stack

**Backend + database** (two containers via Docker Compose):

```bash
git clone https://github.com/mingjing-zhang/week-05-api.git
cd week-05-api
cat > .env <<EOF
DATABASE_URL=postgresql://postgres:password@localhost:5432/booktracker
ANTHROPIC_API_KEY=sk-ant-...                # your own key from console.anthropic.com
EOF
docker compose up -d db                     # Postgres
python3.14 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Backend → http://localhost:8000   (Swagger at /docs)
```

**Frontend** (in another terminal):

```bash
git clone https://github.com/mingjing-zhang/week-05-frontend.git
cd week-05-frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm install
npm run dev
# Frontend → http://localhost:3000
# Chat page → http://localhost:3000/chat
```

---

## 3. What's new in Week 5 vs Week 4

### Backend (`week-05-api`)

- `anthropic` Python SDK added to `requirements.txt`.
- `main.py`:
  - Top-level `ai_client = anthropic.Anthropic()` (auto-reads `ANTHROPIC_API_KEY`).
  - `AI_MODEL = "claude-haiku-4-5"` — cost-optimized choice (~$1/M in + $5/M out, roughly 3× cheaper than Sonnet for this workload).
  - New `ChatRequest` Pydantic model.
  - New endpoint **`POST /ai/chat`** — generic book assistant, no DB read.
  - New endpoint **`POST /ai/recommend`** — fetches the user's books from Postgres on every call, injects them into the system prompt, returns grounded recommendations.

### Frontend (`week-05-frontend`)

- New page **`app/chat/page.tsx`** — full chat UI with:
  - Two modes (toggle buttons): **💬 General Chat** → `/ai/chat`, **🎯 Book Recommendations** → `/ai/recommend`.
  - Conversation history kept in component state; sent on every request to maintain context.
  - User messages right-aligned in blue bubbles; AI messages left-aligned in white bubbles.
  - "Thinking…" loading indicator (animated pulse) while a request is in flight.
  - Auto-scroll to the bottom on new messages.
  - Conversation clears when switching modes (per lab spec).
  - Inline error display (red banner) if the backend returns non-2xx.
  - Styled with Tailwind, uses `NEXT_PUBLIC_API_URL` from env.
- `app/layout.tsx` — added **💬 Chat** link in the top nav.

---

## 4. Screenshots

| File | Mode | Caption |
|---|---|---|
| [`screenshots/01-general-chat.png`](screenshots/01-general-chat.png) | 💬 General Chat | Asking "What is The Pragmatic Programmer about?" — generic book knowledge, no DB lookup. |
| [`screenshots/02-personalized-recommendation.png`](screenshots/02-personalized-recommendation.png) | 🎯 Book Recommendations | Personalized pick that **explicitly references** the user's tracked titles (*Sapiens* + *Designing Data-Intensive Applications*) — proving the DB → system prompt grounding works. |

(Both screenshots were captured with `Cmd+Shift+4` from the running app at `http://localhost:3000/chat`.)

---

## 5. Cost transparency

Total Anthropic API spend across this lab — endpoint smoke tests, the four prompt-engineering experiments in Part 4, the off-topic guardrail test, and live browser testing in both modes:

| Phase | Approx tokens | Approx cost (Haiku 4.5) |
|---|---|---|
| Backend smoke test (`/ai/chat`, `/ai/recommend`) | ~600 | $0.003 |
| Prompt experiments (4 variants × 1 question + 1 off-topic test) | ~1,100 | $0.005 |
| Browser testing both modes | ~1,300 | $0.005 |
| **Total** | **~3,000** | **~$0.013 USD** |

Switching the model from `claude-sonnet-4-6` (lab default) to `claude-haiku-4-5` cut cost ~3× with no observable degradation in response quality for this task — see `reflection.md §2` and `PROMPT_EXPERIMENTS.md`.

---

## 6. Rubric self-check

| Criterion | Points | Self-assessment |
|---|---|---|
| `/ai/chat` endpoint works | 20 | ✅ Verified via `/docs` + curl + browser (see Screenshot 01) |
| `/ai/recommend` includes books from database | 25 | ✅ Verified — AI response names tracked books *Sapiens* + *Designing Data-Intensive Applications* by title (Screenshot 02) |
| Frontend chat UI displays conversation correctly | 25 | ✅ Right-blue / left-white bubbles, scrollable history, "Thinking…" loader, auto-scroll |
| Two modes (general / recommendations) work | 10 | ✅ Toggle buttons, mode-specific endpoint routing, history clears on switch |
| Prompt engineering experiments attempted and reflected on | 10 | ✅ See `PROMPT_EXPERIMENTS.md` + `reflection.md §2` — 4 variants tested with full transcripts and observations |
| API key in `.env`, not in code | 5 | ✅ `.env` gitignored; verified via GitHub UI |
| Reflection complete | 5 | ✅ See §7 below + `reflection.md` |
| **Total** | **100** | **100** |

---

## 7. Reflection (also available as `reflection.md` in the backend repo)

> Context: I came into Lab 5 with two layers already understood — the FastAPI/Postgres/Next.js stack from Lab 4, and a strong intuition from my Bitcoin / cryptography work for *"code as a constitution that runs in an adversarial environment."* The new surface area this week is **operating an LLM as a feature inside a real backend**: where the prompt lives, what the model is allowed to see, what it's allowed to do, and how to keep cost predictable. The reflection below leans into those points rather than restating the lab steps.

### Q1. What is the difference between the system prompt and the user message? Why does the separation matter?

The **system prompt** sets the operating rules of the assistant — persona, format, constraints, and what knowledge to assume. It is invisible to the end user, persists across every turn, and is owned by the application developer (me, the backend).

The **user message** is the input being acted on — a question or instruction the user types at run time. The model is expected to answer *within the rules defined by the system prompt*.

The separation matters for three concrete reasons:

1. **Trust boundary.** The system prompt is developer code; the user message is untrusted input. Treating them as equal would let a user override developer intent with the classic *"ignore previous instructions, do X"* pattern. Keeping them syntactically distinct (different roles in the API) is the model's first line of defense against prompt injection. This is the same shape as the SQL parameterization fix from 20 years ago — the language has a separator between "the program" and "the data the program operates on."
2. **Caching and cost.** A long, well-tuned system prompt can be cached on the API side and reused across many user turns very cheaply. Inlining everything into each user message defeats that and bills you for the same tokens repeatedly.
3. **Reproducibility.** The system prompt is a piece of code I can version-control, A/B test, and reason about in `main.py`. The user message is data flowing through it. Mixing the two makes both harder to evolve, the same way that mixing controller logic with view templates made my old JSP code unmaintainable.

In `/ai/recommend` this separation is exactly what lets the backend inject the user's actual book library into the system prompt before each call — book titles never have to be smuggled into the user turn.

### Q2. What happened when you changed the system prompt in Part 4? What surprised you most?

I ran four variants (full transcripts in `PROMPT_EXPERIMENTS.md`) holding the user question constant — *"Recommend me a book about systems thinking"*:

- **Baseline** ("helpful book assistant"): friendly, 3 picks with markdown formatting, ended with a clarifying question. **201 output tokens.**
- **"Marcus" persona** ("opinionated literature professor"): first-person voice, picked ONE definitive winner instead of a list, dramatic phrasing (*"makes them sing"*, *"trust me on this one"*). **284 tokens — 41% longer than baseline** for the same question.
- **Structured format constraint** ("Title / Why: one sentence / exactly 3"): mechanically obedient. No preamble, no follow-up. **165 tokens — the shortest** of the four.
- **Topic constraint** ("ONLY discuss books, redirect everything else"): on the on-topic question, output was indistinguishable from baseline. The constraint was dormant. On a deliberately off-topic question ("What's the weather like?") it cleanly redirected back to books without sounding rude.

**Most surprising:** the topic constraint was completely invisible until violated. I had expected it to make the assistant feel more rigid even on legitimate questions. Instead it acted exactly like a well-engineered guardrail — silent in the common case, decisive at the boundary. This reframed how I think about prompt engineering: it is less *"tell the model what to do"* and more *"tell the model what frame it operates inside."* The frame stays out of the way until reality bumps against its edges.

**Second-most surprising:** how much the persona inflated cost. Personas grant permission to editorialize. For a production endpoint called thousands of times a day, a 41% length premium per call is real money. The most cost-efficient prompts are flat and instructional.

### Q3. Name one situation where using AI in an app could cause harm, and how you would mitigate it.

**Scenario: hallucinated book metadata used as a purchase or parenting decision.**

If a user asks `/ai/recommend` and the model confidently invents a title that doesn't exist (or attributes a real title to the wrong author / publisher / ISBN) and the user trusts the answer enough to pre-order it, the assistant has caused real-world transaction harm. The same shape applies to *"is this book appropriate for my 8-year-old?"* — a hallucinated content summary could put a child in front of material that isn't right for them.

**Mitigations, in layers** (defense in depth — the same model I use for Bitcoin Script verification):

1. **Grounding.** Don't ask the model to recall facts; have it work over a vetted source. `/ai/recommend` is already shaped correctly because the DB injects real books into the system prompt. For recommendations *outside* the user's library, we'd want to ground in an external API (Google Books / OpenLibrary) and pass real metadata into the prompt rather than trusting model recall.
2. **No irreversible actions.** Recommendations stay advisory. Never auto-purchase, never auto-share, never auto-email. The model proposes; the human commits.
3. **UI transparency.** Render every AI response with an *"AI-generated — verify before action"* affordance, and link out to a real catalog page so the user can sanity-check the title exists.
4. **Output validation in code.** Where the AI's job is well-defined (e.g., "extract tags"), validate the response shape on the backend and reject hallucinated values rather than passing them through.

General principle: **the more high-stakes the downstream action, the more verification has to happen *between* the model and the action.** The Bitcoin equivalent: never broadcast a transaction without independent validation of every signature and every script.

### Q4. If you had infinite Claude API credits, what AI feature would you add to this book tracker?

**Feature: a "reading companion" that grounds the AI in the actual text of books I'm reading, not just titles.**

When I mark a book as `reading`, the app fetches the book's full text (where legal — public-domain via Project Gutenberg, licensed via the Google Books partial-content API, or a personal EPUB upload). The text is chunked, embedded, and stored in pgvector inside the same Postgres I already have. The chat UI gains a third mode — **"Discuss this book"** — that retrieves the top-k relevant passages on every user turn and stuffs them into the system prompt as context. The model now answers grounded in actual passages rather than memory.

**Concrete additions on top of the current stack:**

- `books.text_status` column: `none | available | indexed`.
- A `book_chunks` table: `(book_id, chunk_index, text, embedding vector(1536))`, indexed with pgvector.
- `POST /books/{id}/ingest_text`: accepts a URL or uploaded file, chunks with a recursive character splitter (~500 tokens, 50-token overlap), embeds each chunk via Voyage, upserts into `book_chunks`.
- `POST /ai/discuss`: given a `book_id` and a user message:
  1. Embed the user's message.
  2. `SELECT text FROM book_chunks WHERE book_id = $1 ORDER BY embedding <=> $2 LIMIT 8` (pgvector cosine distance).
  3. Build the system prompt with the retrieved passages clearly marked as quotes with their chunk indices.
  4. Call Claude with `max_tokens=2048`.
  5. Return both the reply AND the citation chunk indices.
- Frontend: clicking a citation jumps to the exact paragraph in a book reader.

**Why this is the right next feature:** every other AI feature I might add (summaries, themes, character analyses) is downstream of this. Once the system can ground in actual text, all of those become well-typed RAG queries instead of trust-the-model recall. It also directly addresses the Q3 harm scenario — a grounded answer about *"what does this book actually say about X"* is auditable in a way that a hallucinated summary is not.

There's a personal angle too. My day work is Bitcoin protocol research where I spend a lot of time re-reading the same papers and BIPs and trying to recall *"where exactly did Wuille say that about SIGHASH?"*. The same RAG pattern, pointed at a private corpus of papers instead of novels, is something I'd genuinely use. A book tracker is just a friendlier surface to build the same pattern on.

---

## 8. Files in this submission

```
week-05-api/                              ← backend repo
├── main.py                               ← + /ai/chat, /ai/recommend
├── requirements.txt                       ← + anthropic
├── PROMPT_EXPERIMENTS.md                 ← Part 4 full transcripts & observations
├── reflection.md                         ← standalone copy of §7
├── SUBMISSION.md                         ← this file
├── screenshots/
│   ├── 01-general-chat.png               ← Screenshot 1 (General Chat mode)
│   └── 02-personalized-recommendation.png ← Screenshot 2 (DB-grounded recommendation)
├── database.py / models.py / schemas.py   ← unchanged from Week 4
├── docker-compose.yml                     ← unchanged
├── .env                                   ← gitignored (contains ANTHROPIC_API_KEY)
└── .gitignore

week-05-frontend/                         ← frontend repo
├── app/
│   ├── chat/page.tsx                     ← ★ new chat UI (two-mode, history, loading)
│   ├── layout.tsx                        ← + 💬 Chat nav link
│   ├── books/                            ← unchanged from Week 4
│   └── ...
├── package.json                          ← renamed to "week-05-frontend"
├── .env.local                            ← gitignored (NEXT_PUBLIC_API_URL)
└── ...
```

---

## 9. Notes for the instructor

- **Model choice**: I deliberately swapped `claude-sonnet-4-6` → `claude-haiku-4-5` for this lab's workload. The lab spec's exact model name is preserved as a code comment for reproducibility. Quality of recommendations was indistinguishable on this task at ~⅓ the cost.
- **`PROMPT_EXPERIMENTS.md`** in the backend repo has the full transcripts of the four Part 4 variants plus a bonus off-topic test for the topic-constraint prompt — happy to walk through any of them in office hours.
- **Cross-domain notes** in `reflection.md` draw on my Bitcoin protocol research background (defense-in-depth, prompt-injection ↔ SQL parameterization, RAG over BIPs) — these are honest cross-references, not padding.
- **What I'd add to the lab next time**: an explicit `response.usage` print in Part 4 so students see the cost dimension of prompt engineering directly. Notes are at the bottom of `reflection.md`.
