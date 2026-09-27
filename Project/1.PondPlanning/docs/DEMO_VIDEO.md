# Demo video — 5 minutes (Phase 3 submission)

Public YouTube, ≤ 5:00. The brief asks the video to explain **the working, the algorithm, and a
demo of the website**. Record the screen at 1920×1080 with the voice-over below. Each scene lists
what is on screen and what to say. Aim for ~130 words a minute. Every number quoted is one the
app shows you live; if the live value differs, say the live one.

**Before recording (2 minutes):**
- `curl http://10.1.75.53:4270/health` → `ok` (or run `make serve-single` locally and use `http://localhost:8080`).
- Open three tabs: the landing page `/`, the planner `/app`, and the report PDF at §4 (Algorithms 1–3).
- In the planner, pre-analyse the sample once so the dropdown has *Khapri*. Everything else is done live.

---

## 0:00 – 0:25 · The problem (landing page)

**Screen:** landing page hero, scroll slowly to "How it works".

> Village ponds store monsoon water, but only where the land actually delivers runoff to them.
> This web app helps a village administrator pick that spot: select the land on a map, and it
> returns the suggested pond location, the catchment that drains to it, and how much water it
> can collect — each with its uncertainty.

## 0:25 – 1:35 · Live demo: select a land area (the Phase 3 requirement)

**Screen:** `/app`. Type *Ralegan Siddhi* → **Go**. Click **Draw area on map**, click two
opposite corners around ~3 × 4 km. Point at the green km² badge. Click **Analyse area**; let
the progress bar run (stage names are visible). When it finishes, hover the results overlay.

> I search for the village and draw a box — two clicks. The area is checked live: between a
> quarter and 25 square kilometres. When I press Analyse, the server reads the Copernicus
> 30-metre elevation model for exactly this box — only the bytes under it — and runs the
> analysis. You can see each stage.
>
> Here is the result. The green dots are five ranked pond sites. Number one is the suggestion;
> the blue polygon is its catchment — every cell whose water flows to that point. The overlay
> gives the pond location, the catchment area with its band, the 75 %-dependable rainfall from
> 45 years of data, the expected runoff volume, and the pond the system sized for it: its
> dimensions, storage, and how often it fills. I didn't click anything else — the pond design
> runs automatically on the top site.

## 1:35 – 3:30 · The algorithm (report figures + map)

**Screen:** report §4.2 Figure / Algorithm 1 (D8 graph), then the map with streams; then
Algorithm 3; then click any other point on the map to get its catchment.

> How is the catchment computed? The elevation grid becomes a graph: each cell is a node, and
> each points to its single steepest-downhill neighbour — that is D8 routing. First we fill the
> pits with the Priority-Flood algorithm so every cell drains. Then the graph is a forest of
> trees flowing to the map edge, and sorting cells from high to low is a topological order. So
> one pass pushes each cell's count to its receiver: that's flow accumulation — the size of
> the subtree. Cells draining more than 5 hectares are the streams you see here.
>
> The catchment of a point is just a reverse breadth-first search: start at the outlet and
> walk up every edge that points into it. If I click anywhere [click], the point is snapped to
> the nearest channel — the distance is shown — and the BFS returns this polygon in about a
> second.
>
> How is the area — the site — chosen? Every stream cell is scored on four criteria: enough
> upstream area to fill a pond but not a river, flat ground, a wet convergent position, and how
> much water a two-metre bund would hold. The weights come from an AHP matrix whose
> consistency ratio is checked. But some things must never happen, so they are hard rules
> first: no site on a river or mapped water body, none within 200 metres of one, and none whose
> catchment runs out of the selected box — because then the area and the volume would be
> underestimates. The same pass that computes accumulation also flags those truncated
> catchments.
>
> Rainfall is 45 years of daily ERA5-Land data; runoff is the SCS curve-number method applied
> to each day and then summed — applying it to yearly totals overestimates three times.

## 3:30 – 4:15 · The provided contour map (Phase 2 route) and validation

**Screen:** select *Khapri* in the dropdown; click site 1; **Design a pond here**. Then show
report Figure 7 (before) vs Figure 3 (after), and Figure 8 (cross-check) briefly.

> The same engine takes the provided contour map through the upload route. On this sample an
> early version put the pond on the bank of the river — the river flows in from outside the
> map, so the accumulation never saw it. Now the Copernicus water-body mask is read for the same
> area and excluded, and the site moves to this tributary: 103 hectares, clear of the river.
> The catchment engine agrees with the independent pysheds library within 2–3 %, and 41
> golden tests check it against terrain with known answers.

## 4:15 – 4:50 · Built to run within the four lab systems

**Screen:** `/docs` (Swagger) for 5 s, then the report §7.1 performance paragraph, then
`infra/lab/nginx-lb.conf`.

> Everything is a REST API with job IDs and progress, documented in Swagger. Heavy work runs
> on bounded worker pools, so a click is never stuck behind an analysis, and a full queue
> answers "try later" instead of falling over. With 20 simultaneous users the area analysis
> took 2 seconds at the median. Replicas run on the lab machines behind an nginx load
> balancer that removes a dead machine from rotation.

## 4:50 – 5:00 · Close

**Screen:** landing page footer with the repository link.

> Every number carries its unit and uncertainty, and every design decision is recorded in the
> repository. Thank you.

---

**Upload:** YouTube → Public, title *AI-based Village Pond Planning System — demo (CSD
Assignment 1)*. Put the link into `docs/report/latex/main.tex` (`\videourl`), rebuild with
`make report-latex`, and add it to `README.md`.
