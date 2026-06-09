/goal

Build a working MVP for an AI-assisted quality detector for Prozorro tender documentation.

The final product must have two parts:

1. Tender Processing System
2. Presentation Engine

The system must process real public Prozorro tenders, analyze their tender documentation, calculate quality scores, detect risky or unclear requirements, and show the results in a usable dashboard.

All user-facing output must be in Ukrainian:
- dashboard UI
- reports
- issue descriptions
- score explanations
- suggested rewrites
- labels, filters, summaries
- README product description

The system must not claim legal violations. Use cautious wording:
- “потенційний ризик”
- “може обмежувати конкуренцію”
- “потребує перевірки людиною”
- “можлива проблема”
- “нечітка вимога”

For each processed tender, produce:
- overall quality score from 0 to 100
- subscores:
  - повнота
  - зрозумілість
  - конкурентність
  - технічна нейтральність
  - якість проєкту договору
- detected issues
- evidence quotes from tender documents
- short Ukrainian explanation
- suggested Ukrainian rewrite
- document parsing status
- limitations / human review notice

Core issue categories:
- restrictive or discriminatory-looking requirements
- brand/model lock-in
- missing “або еквівалент”
- authorization letter / manufacturer dependency
- geographic restrictions
- vague or ambiguous requirements
- excessive qualification requirements
- excessive document requirements
- unclear delivery/payment terms
- weak or incomplete draft contract terms
- scanned or hard-to-use documents

Use live Prozorro data:
- fetch public tenders from Prozorro API
- download public tender documents
- parse PDF/DOCX/TXT/HTML/XLSX where practical
- cache downloaded data

Tender selection:
Each iteration must process 5 new usable tenders.

Default selection rules:
- expected value: 1,000,000–40,000,000 UAH
- was not processed before
- prefer recent tenders
- try to diversify by sector 

Development method:
Iterate on real data.

For each iteration:
1. Fetch 5 new matching tenders.
2. Process them.
3. Open them in the presentation engine.
4. Review actual output:
   - Are scores reasonable?
   - Are evidence quotes correct?
   - Are issue detections useful?
   - Are there obvious false positives?
   - Are important risks missed?
   - Is the Ukrainian clear and natural?
   - Is the dashboard understandable?
5. Improve the processor or presentation engine.
6. Repeat with new tenders.

Run 10 iterations if possible.

Tender Processing System must:
- process one tender by ID
- process a batch of 5 recent matching tenders
- download/cache metadata and documents
- extract text
- detect issues
- calculate scores
- store processed results
- expose results to the presentation engine

Presentation Engine must show:
- list of processed tenders
- title, buyer, value, CPV/sector, processing date
- overall score
- subscores
- number of issues
- highest severity
- detail page per tender
- analyzed documents
- issues grouped by category
- evidence quotes
- explanations
- suggested rewrites
- parsing limitations
- aggregate overview across processed tenders

Prefer:
- deterministic rules first
- simple scoring
- structured stored results

Avoid:
- complex multi-agent systems
- expensive full-document LLM calls
- LLM-only analysis
- hidden chain-of-thought logging
- legal accusations

Final deliverables:
1. Working Tender Processing System.
2. Working Ukrainian Presentation Engine.
3. Processed examples from real Prozorro tenders.
4. README in Ukrainian with setup/run instructions.
5. Basic tests for detection, scoring, tender selection, and storage.

Success condition:
A user can run the system, process live Prozorro tenders, launch the dashboard, see processed tenders, open each tender, and understand its score, issues, evidence quotes, and suggested improvements in Ukrainian.

Start by inspecting the repository, then build the smallest end-to-end processor + dashboard, then improve it through real-data iterations.

Use codex as LLM engine for the tender analysis
