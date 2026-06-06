# Week 5 Reflection — AI-Powered Book Assistant

Context for this week: I came into Lab 5 with two layers already understood — the FastAPI/Postgres/Next.js stack from Lab 4, and a strong intuition from my Bitcoin / cryptography work for "code as a constitution that runs in an adversarial environment." The new surface area this week is **operating an LLM as a feature inside a real backend**: where the prompt lives, what the model is allowed to see, what it's allowed to do, and how to keep cost predictable. The reflection below leans into those points rather than restating the lab steps.

---

## 1. What is the difference between the system prompt and the user message? Why does the separation matter?

The **system prompt** sets the operating rules of the assistant — persona, format, constraints, and what knowledge to assume. It is invisible to the end user, persists across every turn, and is owned by the application developer (me, the backend).

The **user message** is the input being acted on — a question or instruction the user types at run time. The model is expected to answer *within the rules defined by the system prompt*.

The separation matters for three concrete reasons:

1. **Trust boundary.** The system prompt is developer code; the user message is untrusted input. Treating them as equal would let a user override developer intent with the classic *"ignore previous instructions, do X"* pattern. Keeping them syntactically distinct (different roles in the API) is the model's first line of defense against prompt injection. This is the same shape as the SQL parameterization fix from 20 years ago — the language has a separator between "the program" and "the data the program operates on."
2. **Caching and cost.** A long, well-tuned system prompt can be cached on the API side and reused across many user turns very cheaply. Inlining everything into each user message defeats that and bills you for the same tokens repeatedly.
3. **Reproducibility.** The system prompt is a piece of code I can version-control, A/B test, and reason about in `main.py`. The user message is data flowing through it. Mixing the two makes both harder to evolve, the same way that mixing controller logic with view templates made my old JSP code unmaintainable.

In `/ai/recommend` this separation is exactly what lets the backend inject the user's actual book library into the system prompt before each call — book titles never have to be smuggled into the user turn.

---

## 2. What happened when you changed the system prompt in Part 4? What surprised you most?

I ran four variants (see `PROMPT_EXPERIMENTS.md` for full transcripts) holding the user question constant ("Recommend me a book about systems thinking"):

- **Baseline** ("helpful book assistant"): friendly, 3 picks with markdown formatting, ended with a clarifying question. 201 output tokens.
- **Marcus persona** ("opinionated literature professor"): adopted a first-person voice, picked ONE definitive winner instead of a list, used dramatic phrasing ("makes them sing", "trust me on this one"). **284 tokens — 41% longer than baseline** for the same question.
- **Structured format constraint** ("Title / Why: one sentence / exactly 3"): mechanically obedient. No preamble, no follow-up question. **165 tokens — the shortest** of the four.
- **Topic constraint** ("ONLY discuss books, redirect everything else"): on the on-topic question, the output was indistinguishable from baseline. The constraint was dormant. When I asked it about the weather, it cleanly redirected back to books without sounding rude.

**What surprised me most:** the topic constraint was completely invisible until violated. I had expected it to make the assistant feel more rigid even on legitimate questions. Instead it acted exactly like a well-engineered guardrail — silent in the common case, decisive at the boundary. This reframed how I think about prompt engineering: it is less "tell the model what to do" and more "tell the model what frame it operates inside." The frame stays out of the way until reality bumps against its edges.

The second-most surprising thing was how much the persona inflated cost. Personas grant permission to editorialize. For a production endpoint where this gets called thousands of times a day, a 41% length premium per call is real money. The most cost-efficient prompts are flat and instructional.

---

## 3. Name one situation where using AI in an app could cause harm, and how you would mitigate it.

**Scenario: hallucinated book metadata used as a purchase or parenting decision.**

If a user asks `/ai/recommend` for a book and the model confidently invents a title that doesn't exist (or attributes a real title to the wrong author / publisher / ISBN), and the user trusts the answer enough to buy or pre-order it, the assistant has caused a real-world transaction harm — money spent on something fictional. The same shape of failure applies to *"Is this book appropriate for my 8-year-old?"* — a hallucinated content summary could put a child in front of material that isn't right for them. The harm here is not exotic; it's the ordinary cost of treating model output as truth without verification.

**Mitigations, in layers** (this layered model is the same way I think about Bitcoin Script verification — defense in depth):

1. **Grounding.** Don't ask the model to recall facts; have it work over a vetted source. `/ai/recommend` is already shaped correctly because the DB injects real books into the system prompt. For recommendations *outside* the user's library, we'd want to ground in an external API (Google Books, OpenLibrary) and pass real metadata into the prompt rather than trusting model recall.
2. **No irreversible actions.** Recommendations stay advisory. Never auto-purchase, never auto-share, never auto-email. The model proposes; the human commits.
3. **UI transparency.** Render every AI response with an "AI-generated — verify before action" affordance, and link out to a real catalog page so the user can sanity-check the title exists.
4. **Output validation in code.** Where the AI's job is well-defined (e.g., "extract tags"), validate the response shape on the backend and reject hallucinated values rather than passing them through.

The general principle: the more high-stakes the downstream action, the more verification has to happen *between* the model and the action. The Bitcoin equivalent is: never broadcast a transaction without independent validation of every signature and every script.

---

## 4. If you had infinite Claude API credits, what AI feature would you add to this book tracker? Describe it technically.

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

**Why this is the right next feature:** every other AI feature I might add (summaries, themes, character analyses) is downstream of this. Once the system can ground in actual text, all of those become well-typed RAG queries instead of trust-the-model recall. It also directly addresses the harm scenario from Q3 — a grounded answer about *"what does this book actually say about X"* is auditable in a way that a hallucinated summary is not.

There's a personal angle too. My day work is Bitcoin protocol research where I spend a lot of time re-reading the same papers and BIPs and trying to recall *"where exactly did Wuille say that about SIGHASH?"*. The same RAG pattern, pointed at a private corpus of papers instead of novels, is something I'd genuinely use. A book tracker is just a friendlier surface to build the same pattern on.

---

## What I'd change about this lab if I taught it

Two notes for next iteration:

1. **Make the cost dimension explicit.** Walking the student through "this experiment cost me $0.005 in Haiku tokens" turns prompt engineering from a vibes activity into an engineering one. I'd add a small block in Part 4 that prints `response.usage` and discusses it.
2. **Encourage swapping models, not just prompts.** I switched the production model to `claude-haiku-4-5` instead of the spec's `claude-sonnet-4-6` for this lab's volume. The same prompt produces different *shapes* of answer on different models, not just different qualities. That's a useful intuition to develop alongside prompt engineering.
