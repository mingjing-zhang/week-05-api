# Week 5 Lab — Part 4: Prompt Engineering Experiments

**Model**: `claude-haiku-4-5`
**Same user question across all variants**: *"Recommend me a book about systems thinking."*
**Goal**: Hold the user message constant; vary the system prompt; observe how output shape, persona, and constraints shift.

---

## Variants tested

### Baseline (current `/ai/chat` system prompt)
> *"You are a helpful book assistant for a personal book tracking app. Help users discover books, discuss what they've read, and get personalized recommendations. Be conversational, enthusiastic about books, and concise."*

**Output (201 tokens):** Friendly, multi-recommendation format, ends with a clarifying follow-up question. Uses markdown bullets and bold for titles. Tone: helpful generalist.

### Experiment 1 — Opinionated persona ("Marcus")
> *"You are Marcus, a passionate and opinionated literature professor who has strong views about books. You're enthusiastic and sometimes dramatic."*

**Output (284 tokens, +41% vs baseline):** Persona-driven. First person voice ("I find", "Trust me on this one"). Picks ONE definitive top recommendation rather than a list. Uses dramatic phrasing ("makes them sing", "fundamentally changes how you understand everything"). Length grew because the persona invites editorializing.

### Experiment 2 — Structured format constraint
> *"When recommending books, always format your response as: **Title** by Author / Why: One sentence on why they'd like it. Give exactly 3 recommendations unless asked for a different number."*

**Output (165 tokens, -18% vs baseline):** Mechanically obedient. Exactly 3 entries. Each has exactly the prescribed shape. No follow-up question, no editorializing, no preamble. **Shortest of the four** by far. The shape was respected even though the content choices were similar to the baseline.

### Experiment 3 — Topic constraint (books only)
> *"You are a book assistant. You ONLY discuss books and reading. If asked about anything else, politely redirect back to books."*

**Output (285 tokens) on the on-topic question:** Looks almost identical to the baseline. The constraint is dormant when not violated.

**Off-topic test — "What's the weather like?":** Polite redirect (*"I appreciate the question, but I'm specifically here to help with books and reading!"*) followed by a menu of book-related things it CAN help with. Constraint enforced cleanly without sounding rude.

---

## Observations

1. **The system prompt sets the operating rules; the user message is the operand.** Same user message, four different outputs. The system prompt acts like a constitution — invisible to the user, persistent across the conversation, shaping every reply.

2. **Personas inflate length.** The Marcus persona produced ~41% more tokens than the baseline for the same question, because adopting a "passionate professor" voice grants permission to editorialize. **Practical takeaway:** if cost matters, neutral system prompts are cheaper.

3. **Format constraints compress output.** Experiment 2 was the *shortest* response. Telling the model "exactly 3, this template" eliminates the model's default tendency to wrap recommendations in friendly context.

4. **Negative constraints (Experiment 3) are dormant until triggered.** "ONLY discuss books" had no visible effect on the on-topic question — the response looked like the baseline. But the moment we asked about weather, the constraint became the entire response. **This is the right model for safety guardrails: invisible when not needed, decisive when needed.**

5. **Cost of these 5 experiments**: roughly 1,100 total tokens ≈ **$0.005 USD** on Haiku 4.5. Iterating on prompts is essentially free.

## Final choice (restored)

Kept the baseline ("helpful book assistant") for production. It balances readability, length, and friendliness. The Marcus persona would be fun as an optional "mode" alongside the existing two — noted as a future improvement in `reflection.md`.

## Full transcripts

Raw output of all 5 calls saved to `/tmp/prompt_experiments.txt` during the run. The summaries above are excerpted from that file.
