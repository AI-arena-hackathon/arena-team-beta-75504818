# SeniorCare Pulse

Team beta — spec §3.2 hackathon build.

**One-liner:** AI‑powered, low‑tech analytics that help community centers turn senior‑population data into real‑time, actionable programs

**Problem:** Community centers and local health agencies lack a user‑friendly way to interpret demographic and engagement data for senior citizens, leading to generic programs that miss key needs and low participation rates.

**Solution:** A lightweight web app that ingests publicly available census data, local health records, and center‑specific participation logs. It uses AI to surface pain points (e.g., unmet mobility support, low digital engagement), recommends targeted programs (e.g., low‑tech exercise classes, mobile health check‑ins), and provides an interactive dashboard with simple action‑checklists for staff. The platform runs on a shared browser kiosk with voice prompts for seniors who are not tech‑savvy.

**Build scope:** **SeniorCare Pulse – Day 4‑5 Architecture**

**Tech stack**  
- **Frontend:** React 18 + Material‑UI, hosted on a local Apache 2 kiosk; voice prompts via Web Speech API.  
- **Backend:** Flask 2.3 REST API, containerized with Docker, running on the center’s on‑premise server (no internet required).  
- **Data layer:** SQLite 3 (portable file), pre‑loaded with census, health‑agency CSVs and the center’s participation logs.  

**Core components**  

| # | Component | Responsibility |
|---|-----------|----------------|
| 1 | **Ingestion Service** (Flask) | Scheduled CSV import, schema validation, simple deduplication; exposes `/data/refresh`. |
| 2 | **Analytics Engine** (Python module) | Runs nightly K‑Nearest‑Neighbors clustering (scikit‑learn), stores cluster IDs and confidence scores in SQLite, generates “pain‑point” tags. |
| 3 | **Dashboard UI** (React) | Fetches `/clusters` endpoint, renders interactive cards per cluster, shows recommended programs, and provides “Mark‑Done” checklists that write back to SQLite via `/action`. |

**Top 2 risks**  
1. **Data privacy / PHI leakage** – health agency files may contain protected information. *Mitigation:* enforce on‑premise deployment, strip identifiers during ingestion, and lock down network access.  
2. **Usability for low‑tech seniors** – staff may misinterpret dashboard outputs. *Mitigation:* voice‑guided walkthroughs, large UI fonts, and a printed “quick‑start” cheat sheet.

**Fallback scope (if schedule slips)**  
- Replace KNN with simple rule‑based grouping (age + mobility flag).  
- Drop voice prompts; provide a static audio file button.  
- Use a single HTML page with embedded JSON instead of full React build.

Built entirely by an AI coding agent across discrete GitHub Actions build turns (spec §8) — no human-written code.
