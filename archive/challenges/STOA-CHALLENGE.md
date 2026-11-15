# Stoa — "Make Blueprints Talk"

Build a program that answers natural language questions about construction drawings and building information models accurately and verifiably.

## Framing
Construction site engineers spend hours every day looking for information. **General-purpose AI models frequently fail when analyzing complex technical drawings.** Stoa calls this "one of the hardest unsolved problems in construction tech" and wants to see what a fresh approach can do with real data.

## The ask
Create a program answering **natural language questions about construction drawings**. You get a dataset of **real technical drawings in many formats and languages** together with example questions.

**A great answer is correct and shows where in the drawing it came from, so a human can verify it in seconds.**

They are interested in solutions **next year's frontier models won't make obsolete** — for example hybrid approaches combining frontier models with **computer vision, 3D, geometry, or small fine-tuned models**.

## Data provided
Comprehensive dataset of real construction drawings and models:
- **Preview (0.5 GB):** https://fwjydgxpttajiqpfmqtj.supabase.co/storage/v1/object/public/stoa-junction-2026/junction-dataset-preview.zip
- **Full dataset (10 GB):** https://fwjydgxpttajiqpfmqtj.supabase.co/storage/v1/object/public/stoa-junction-2026/junction-dataset.zip

## Mentors
Stoa's founding tech team — engineers working on construction AI daily — plus a construction engineer with years of experience on large building projects.

## About Stoa
Building the AI-native operating system for construction, a $15 trillion industry (~13% of world GDP). Helsinki-based, backgrounds at Supercell, AWS, McKinsey, Slush, Wave Ventures, SRV and Sensofusion. Already working with several of the largest Nordic construction companies. Backed by Lifeline Ventures, the founders of Wolt, Supercell and SiloAI, plus two former Y Combinator partners; recently raised Finland's largest-ever pre-seed round.

## Implications for how we build
- **No published judging rubric** in this brief. Ask at the booth; otherwise optimise for the two things they state explicitly: **accuracy** and **verifiable provenance** (pointing at the region of the drawing the answer came from).
- **"Shows where in the drawing it came from" is the differentiator.** A RAG-over-PDF-text answer with no spatial grounding misses the stated bar. Bounding-box or region highlighting on the drawing is the feature that makes the demo land.
- **"Solutions next year's frontier models won't make obsolete"** is a direct hint against a thin wrapper around a VLM. They want geometry/CV/structural reasoning that adds something a bigger model wouldn't subsume.
- **10 GB of real multi-format, multi-language drawings** — download the preview immediately and inspect formats before designing anything. Expect PDFs, possibly DWG/IFC. IFC (BIM models) is structured and queryable; raster drawings are not. Which formats dominate changes the whole approach.
- Multi-language content means text extraction alone is fragile; symbols and geometry are language-independent and may be more reliable.
- This is the most technically demanding of the briefs collected, and also the one where a partial solution on a narrow question type (e.g. "how many of X on this floor") could still demo convincingly if provenance is solid.
