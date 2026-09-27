# Demo video — how to record it, and the script to narrate

**Target:** one public YouTube video, **4:30–4:50 long** (hard limit 5:00), showing the working
system, the algorithm, and a live demo of the website. The narration below is **about 600
words**, which is 4 min 40 s at a relaxed ~130 words per minute. Read it as written; the
bracketed lines tell you what to do on screen while you say it.

---

## Part 1 — Before you record (15 minutes, once)

**Tools (Mac):** QuickTime Player → *File → New Screen Recording* → *Options → Microphone:
your mic* → record the **whole screen**. (OBS Studio works too.) Use earphones with a mic or
a quiet room; do one 10-second test and listen back.

**Screen:**
1. Close every other app and notification (*Focus → Do Not Disturb*).
2. Chrome, full-screen (`Ctrl+Cmd+F`), zoom **100 %**, no bookmarks bar (`Cmd+Shift+B`).
3. Open these tabs, in this order:
   - Tab 1 — `http://10.1.75.53:4272/` (landing page)
   - Tab 2 — `http://10.1.75.53:4272/app` (planner)
   - Tab 3 — `docs/report/Final_Report.pdf`, opened at **Figure 3** (the flowchart, page 5)
   - Tab 4 — the same PDF at **Algorithm 1** (page 6)
   - Tab 5 — `http://10.1.75.53:4272/docs` (Swagger)
4. **Warm up the site** so nothing is slow on camera: in Tab 2 do one full run of Scene 2
   (search Ralegan Siddhi, draw, analyse), then **reload the page** so it starts clean.
5. Check it is alive: `curl http://10.1.75.53:4272/lb/health` → `ok`. Off campus, run
   `make serve-single` locally and use `http://localhost:8080` instead.

**Rehearse once with a timer.** If you are over 5:00, drop the sentences marked *(optional)*.

---

## Part 2 — Scenes and narration

### Scene 1 · 0:00–0:25 · Who and what — *Tab 1, landing page*

[Start on the landing page hero. Scroll slowly down to "How it works".]

> Hello, I am Rahul Raj, student ID 12341680, IIT Bhilai. This is my AI-based Village Pond
> Planning System. A village pond only works where the land actually sends rainwater to it.
> This web app finds that place: you select the land on a map, and it returns the best pond
> location, the catchment that drains into it, and how much water it can collect.

### Scene 2 · 0:25–1:35 · Live demo: selecting the land — *Tab 2, planner*

[Click the search box, type **Ralegan Siddhi**, click **Go**. Wait for the map to fly there.]

> I start by finding the village.

[Click **Draw area on map**. Click the top-left corner of the farmland, then the bottom-right —
about 3 to 4 km across. Point the mouse at the green km² badge.]

> I draw a box around the land with two clicks. The area is checked immediately — it has to
> be between a quarter and twenty-five square kilometres.

[Click **Analyse area**. Let the progress bar run; do not talk over the first two seconds.]

> When I press Analyse, the server downloads the thirty-metre Copernicus elevation model for
> exactly this box, and runs the analysis. You can see each stage as it happens.

[Results appear. Move the mouse slowly: green dots → blue polygon → results panel.]

> These green dots are five ranked pond sites. Number one is the suggestion. The blue shape is
> its catchment — every piece of land whose rain flows to that point. The panel shows the
> catchment area, the rainfall I can expect three years out of four, the expected runoff
> volume, and a pond sized for it — its dimensions, storage, and how often it fills.
> Every number has its uncertainty next to it.

### Scene 3 · 1:35–3:15 · The algorithm — *Tab 3 (flowchart), Tab 4 (Algorithm 1), then Tab 2*

[Switch to Tab 3, Figure 3. Trace the path with the mouse as you speak.]

> Here is how it works. Whether I draw a box or upload a contour map, I get an elevation grid.
> First, the Priority-Flood algorithm fills small pits, so that every cell can drain.

[Switch to Tab 4, Algorithm 1.]

> Then each cell points to its steepest downhill neighbour — this is called D8 flow routing.
> That turns the whole map into a graph: a forest of trees flowing towards the edges. If I
> sort the cells from highest to lowest, that order is a topological order of the graph, so
> a single pass adds up how many cells drain through each one. That is flow accumulation. The
> same pass also marks cells whose catchment runs out of the selected box.

[Switch to Tab 2. Click anywhere on a stream on the map; the catchment redraws.]

> The catchment of any point is a reverse breadth-first search: start at the point and walk
> uphill along every arrow that flows into it. When I click anywhere, the point is snapped to
> the nearest stream, and the search returns the catchment in about a second.

[Point back at the ranked sites.]

> To choose the site, every stream cell gets a score from four things: enough upstream area to
> fill a pond but not a river, flat ground, a wet valley position, and how much water a small
> embankment would hold. Before scoring, some places are ruled out completely: rivers, mapped
> water, a two-hundred-metre belt around them, and any site whose catchment is cut by the edge
> of the box.

> Rainfall comes from forty-five years of daily data. Runoff uses the SCS curve-number method
> on every single day, then adds them up.

### Scene 4 · 3:15–4:05 · The provided contour map and validation — *Tab 2*

[Open the village dropdown at the top and choose **Khapri · Durg**. Click site **1** in
*Suggested sites*, then **Design a pond here**. Wait for the panel.]

> The same engine takes the provided contour map. An early version put this pond on the bank
> of the river, because the river flows in from outside the map. Now the Copernicus water
> mask is read for the same area, and the site moved to this tributary — a hundred and three
> hectares, well clear of the river.

> To check the engine, I compared it with an independent library, pysheds: the catchments
> agree within two to three percent. Forty-one tests check it on terrain with known answers.

### Scene 5 · 4:05–4:40 · Built for the four lab machines — *Tab 5, Swagger*

[Show Swagger; scroll past `/analyzeArea` and `/jobs/{id}`.]

> Everything is a REST API, documented here. Long work runs as background jobs on separate
> worker pools, so a click is never stuck behind a big analysis, and a full queue says "try
> later" instead of crashing. The app runs on all four lab machines behind an nginx load
> balancer. With twenty users at once, an area analysis took about two seconds.

### Scene 6 · 4:40–4:50 · Close — *Tab 1, scroll to the footer*

> The code, the report and every design decision are in the GitHub repository. Thank you.

[Stop recording.]

---

## Part 3 — After recording

1. **Trim** the start and end in QuickTime (*Edit → Trim*). Check the length is **under 5:00**.
2. **Export** 1080p (*File → Export As → 1080p*).
3. **Upload** to YouTube:
   - Title: *AI-based Village Pond Planning System — Demo (CSD Assignment 1, Rahul Raj, 12341680)*
   - Visibility: **Public** (the brief asks for a public link, not unlisted).
   - Description: the GitHub link and the site URL `http://10.1.75.53:4272`.
4. Open the video in a private/incognito window to confirm anyone can watch it.
5. Send me the link. I'll put it into the report (`\videourl` in
   `docs/report/latex/main.tex`), rebuild the PDF, and add it to the README.

**If something goes wrong while recording:** keep going and re-record just that scene; join
the clips in iMovie. If the analysis is slow on the day, say "the server is fetching the
elevation data" and wait — it is honest and it is what is happening.
