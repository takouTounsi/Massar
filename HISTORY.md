# Git History

This file preserves the repository history before republishing the project
without its `.git` directory.

It was generated from the local Git metadata on branch `main`.

- Captured branch: `main`
- Captured HEAD: `8ee4c3bb37277e9968e54cd7db7eccd8964eb6c3`
- Commit count: 49
- First commit date: `2026-06-17`
- Last commit date: `2026-06-25`

Original command used for the compact timeline:

```bash
git log --reverse --date=short --pretty=format:"%h %ad %an %s"
```

## Contributors In Git Log

```text
17 AhmedLoubiri
 9 Ahmed Loubiri
 7 takouTounsi
 7 Medmas07
 6 kmarBenAyed
 4 mohannedbt
 1 takou_tounsi
```

## Project Evolution Summary

Massar started on `2026-06-17` as a service-oriented MVP for entrepreneurial
orientation, with FastAPI services, shared contracts, rules, synthetic data,
Docker Compose, a React frontend and early documentation.

The first phase established the monorepo, service boundaries, architecture
documents, domain models, scoring, maturity, blocker detection, eligibility,
resources, roadmap generation, database migrations and tests.

The second phase, mainly on `2026-06-23`, added scraped or generated guidance
data, restored the dedicated classification service, introduced a larger
scoring module, improved the frontend, added authentication and 2FA, enabled
Arabic language support, connected Groq/Gemini-related LLM helpers, and linked
the classification PML flow to the adaptive intake engine.

The third phase, mainly on `2026-06-24`, expanded the frontend into a richer
demo experience: dashboard, roadmap, scores, resources, journey, intelligence
views, animation contracts, weakest-link score explanations, confidence UI,
stage rails, counterfactual hover interactions and resource filtering.

The final phase on `2026-06-25` focused on integration and polish: connecting
classification to the frontend, fixing auth reload behavior, refining login and
register layouts, updating environment examples, adding evaluation artifacts,
benchmark scripts, generated reports, RAG/evaluation documentation and detailed
Mermaid architecture documentation.

## Chronological Commit Timeline

| Commit | Date | Author | Subject |
| --- | --- | --- | --- |
| `7877a4d` | 2026-06-17 | takouTounsi | first commit |
| `4c3a487` | 2026-06-17 | takouTounsi | README update |
| `264e576` | 2026-06-17 | takouTounsi | README fix |
| `c9876d0` | 2026-06-17 | takou_tounsi | Rename project to MASSAR and revise description |
| `ab70c84` | 2026-06-23 | kmarBenAyed | scraping business guidance data |
| `7d87fbd` | 2026-06-23 | mohannedbt | Remove mirrored classifier from intake_service; restore classification_service |
| `2a25bca` | 2026-06-23 | kmarBenAyed | scoring module |
| `d17ea10` | 2026-06-23 | takouTounsi | frontend improved , authentification added(+2FA to test) , Roadmap generation small tested |
| `87cf41d` | 2026-06-23 | AhmedLoubiri | feat(intake-engine): real LLM extraction by default + runtime ledger->diagnosis handoff |
| `86ce356` | 2026-06-23 | takouTounsi | frontend some bugs fixed |
| `bcd99ea` | 2026-06-23 | takouTounsi | 2FA bug fixed |
| `0d39426` | 2026-06-23 | takouTounsi | 2FA QR-code added |
| `4d708a2` | 2026-06-23 | Medmas07 | ARAbe language supported |
| `7da6c21` | 2026-06-23 | kmarBenAyed | fixed the groq model to generate sectors kb and added some enhancements |
| `b7ee2f2` | 2026-06-23 | AhmedLoubiri | feat(intake-engine): integrate classification service's PML to the adaptive intake engine |
| `c55bb24` | 2026-06-23 | Ahmed Loubiri | Merge branch 'dev' into feat/Start_Classification |
| `9a81f45` | 2026-06-23 | Ahmed Loubiri | Merge pull request #2 from Medmas07/feat/Start_Classification |
| `3998900` | 2026-06-24 | Medmas07 | security dataset added |
| `1417505` | 2026-06-24 | AhmedLoubiri | feat(frontend): some ui enhancements |
| `96b9d1d` | 2026-06-24 | mohannedbt | feat/added 6 phases instead of 5 |
| `715b2fc` | 2026-06-24 | mohannedbt | readme |
| `b57660d` | 2026-06-24 | AhmedLoubiri | fix(frontend): change the roadmap page ui |
| `aca166d` | 2026-06-24 | AhmedLoubiri | feat(frontend): phase 0 - add framer-motion + shared animation contract |
| `f13d06c` | 2026-06-24 | AhmedLoubiri | feat(frontend): phase 1 - persistent StageRail, ConfidenceRing, header readiness/gap chips + sector badge |
| `448c787` | 2026-06-24 | AhmedLoubiri | feat(frontend): phase 2 - Scores page with weakest-link cascade, lambda tooltip, how-calculated disclosure |
| `44f5f7b` | 2026-06-24 | AhmedLoubiri | feat(frontend): phase 3 - roadmap unlock beat + counterfactual hover |
| `a30effb` | 2026-06-24 | AhmedLoubiri | feat(frontend): phase 4 - resources filters/relevance, journey ring + stage-gate, intelligence bottleneck/leverage |
| `a49ab26` | 2026-06-24 | AhmedLoubiri | feat(frontend): phase 5 - dashboard cascade reveal + cleanup |
| `e3c9102` | 2026-06-24 | Ahmed Loubiri | Merge pull request #1 from Medmas07/scoring_module |
| `16f1ada` | 2026-06-24 | Ahmed Loubiri | Merge branch 'main' into dev |
| `0fc13a5` | 2026-06-24 | Ahmed Loubiri | Merge pull request #3 from Medmas07/adaptive intake engine + classification service |
| `8a5c68a` | 2026-06-24 | Ahmed Loubiri | Merge branch 'main' into frontend_improved |
| `ac4d778` | 2026-06-24 | Ahmed Loubiri | Merge pull request #4 from Medmas07/UI |
| `aec4ed4` | 2026-06-24 | kmarBenAyed | Merge branch 'main' of https://github.com/Medmas07/Massar into front |
| `a411e4c` | 2026-06-24 | kmarBenAyed | new-front |
| `01067ec` | 2026-06-24 | AhmedLoubiri | fix: add missing imports |
| `2974eb3` | 2026-06-24 | kmarBenAyed | Merge branch 'main' of https://github.com/Medmas07/Massar into front |
| `02623ee` | 2026-06-24 | AhmedLoubiri | fix: changed ui of auth and intake engine |
| `938c5fd` | 2026-06-25 | AhmedLoubiri | link the classification service to the frontend |
| `aa9746e` | 2026-06-25 | AhmedLoubiri | fix auth reload issue, restyle the auth and intake pages |
| `3a7419f` | 2026-06-25 | AhmedLoubiri | update .env.example |
| `361d1ba` | 2026-06-25 | Ahmed Loubiri | Merge pull request #5 from Medmas07/front |
| `cdd76e1` | 2026-06-25 | AhmedLoubiri | fix(frontend): center the headline + stages block in login and signup pages |
| `c84b12c` | 2026-06-25 | AhmedLoubiri | fix(frontend): center the content of both login and register |
| `10be0b9` | 2026-06-25 | Medmas07 | some fixs |
| `a62089c` | 2026-06-25 | Ahmed Loubiri | Merge pull request #6 from Medmas07/front-fixes |
| `77fd4fc` | 2026-06-25 | Medmas07 | rag added |
| `34be769` | 2026-06-25 | Medmas07 | Merge branch 'main' of https://github.com/Medmas07/Massar |
| `8ee4c3b` | 2026-06-25 | Medmas07 | ARchitecture added |

## Preserved Provenance Note

If this project is republished as a clean repository, the commit graph itself
will no longer be present. This file keeps the public development chronology in
plain text so readers can still understand how the MVP was built.
