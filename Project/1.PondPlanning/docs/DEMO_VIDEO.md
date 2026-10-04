# Demo video — how to record it, and the script to narrate

**Target:** one public YouTube video, **4:30–4:50 long** (hard limit 5:00), showing the working
system, the algorithm, and a live demo of the website. The narration below is **about 770
words in simple English**, written for a quick speaking pace (~160 words per minute ≈ 4 min
45 s). Read it as written; the bracketed lines tell you what to do on screen while you say it.
Short sentences on purpose: say each one, then move on.

---

## Part 1 — Before you record (15 minutes, once)

**Tools (Mac):** QuickTime Player → *File → New Screen Recording* → *Options → Microphone:
your mic* → record the **whole screen**. (OBS Studio works too.) Use earphones with a mic or
a quiet room; do one 10-second test and listen back.

**Screen:**
1. Close every other app and notification (*Focus → Do Not Disturb*).
2. Chrome, full-screen (`Ctrl+Cmd+F`), zoom **100 %**, no bookmarks bar (`Cmd+Shift+B`).
3. Open these tabs, in this order:
   - Tab 1 — `http://localhost:8765/` (landing page)
   - Tab 2 — `http://localhost:8765/app` (planner)
   - Tab 3 — `docs/report/Final_Report.pdf`, opened at **Figure 3** (the flowchart, page 5)
   - Tab 4 — the same PDF at **Algorithm 1** (page 6)
   - Tab 5 — `http://localhost:8765/docs` (Swagger)
4. **Warm up the site** so nothing is slow on camera: in Tab 2 do one full run of Scene 2
   (search Ralegan Siddhi, draw, analyse), then **reload the page** so it starts clean.
5. **Run it on your Mac** (your Mac reaches every data source; the lab network often cannot):
   in the project folder run `make serve-single`, leave that terminal open, and check
   `http://localhost:8765/health` shows `ok`. Stop it afterwards with `Ctrl+C`.

**Rehearse once with a timer.** If you are over 5:00, drop the last paragraph of Scene 3
("Last step: water") and the second paragraph of Scene 4 — the rest still covers every item.

---

## Part 2 — Scenes and narration

### Scene 1 · 0:00–0:25 · Who and what — *Tab 1, landing page*

[Start on the landing page. Scroll slowly down to "How it works".]

> Hello. I am Rahul Raj, student ID 12341680, from IIT Bhilai. This is my AI-based Village
> Pond Planning System. A village pond is useful only if rain water actually flows into it.
> Finding that spot by hand needs maps, rainfall data and many calculations. My web app does
> it in a few seconds.

### Scene 2 · 0:25–1:30 · Live demo: selecting the land — *Tab 2, planner*

[Click the search box, type **Ralegan Siddhi**, click **Go**. Wait for the map to fly there.]

> Let me show you. First, I search for a village. Here is Ralegan Siddhi in Maharashtra.

[Click **Draw area on map**. Click the top-left corner of the farmland, then the bottom-right —
about 3 to 4 km across. Point the mouse at the green km² badge.]

> Now I select the land. I click one corner, then the opposite corner. That makes a box. The
> app checks the size right away. It must be between a quarter and twenty-five square
> kilometres — about the size of a village.

[Click **Analyse area**. Let the progress bar run.]

> I click Analyse. The server downloads the height of the ground for this box, from the free
> Copernicus satellite data. The progress bar shows each step.

[Results appear. Move the mouse slowly: green dots → blue shape → results panel.]

> Here is the result. The green dots are the five best places for a pond. Number one is the
> best. The blue shape is its catchment — all the land where rain flows to this pond. The
> panel shows the catchment area, the rain we can expect in three out of four years, how much
> water will flow in, the pond size, and how often it fills. Every number has a plus-minus
> to show how sure we are.

### Scene 3 · 1:30–3:15 · The algorithm, step by step — *Tab 3 (flowchart), Tab 4 (Algorithm 1), then Tab 2*

[Switch to Tab 3, Figure 3 — the flowchart. Move the mouse along the boxes as you speak.]

> Now, how does it work? This chart shows the whole process. Read it from top to bottom.
> There are two ways to start. I can draw a box, or I can upload a contour map file. The red
> boxes are safety checks. If the box is too big, or the file has no height data, the app
> stops and says why. It never guesses.

> Both ways give the same thing: a grid of the land, where each small square knows its
> height. Each square is thirty metres wide.

[Point at "Priority-Flood".]

> Step one: fill the small holes. Real ground has small pits. Water would get stuck there,
> so I fill them first. This is the Priority-Flood algorithm. After this, water can always
> flow downhill from every square.

[Switch to Tab 4 — Algorithm 1.]

> Step two: find where water goes. Each square sends its water to the lowest of its eight
> neighbours. This is called D8. Now the map becomes a graph, like many small trees. All the
> water flows down the branches to the trunk.

> Step three: count the water. I sort all squares from highest to lowest. Then I go through
> them once. Each square gives its count to the square below it. So a square in a valley
> collects the count of every square above it. This is flow accumulation. Where the count is
> big, there is a stream.

[Switch to Tab 2. Click on a stream on the map; the blue shape redraws.]

> Step four: the catchment. When I click any point, the app walks uphill from it, like a
> breadth-first search, and collects every square that drains to that point. That is the blue
> shape. It takes about one second.

[Point back at the green dots.]

> Step five: choose the pond site. Every stream square gets a score. It needs enough land
> above it to fill a pond, but not so much that it is a river. It should be flat, wet, and in
> a valley that can hold water. Some places are never allowed: rivers, lakes, two hundred
> metres around them, and places whose catchment goes outside the box. The top score wins.

> Last step: water. The app takes forty-five years of daily rainfall. It uses the SCS curve
> number method, which says how much rain runs off the ground and how much soaks in. It does
> this for every day, then adds them up. That gives the water volume and the pond size.

### Scene 4 · 3:15–4:05 · The provided contour map and testing — *Tab 2*

[Open the village dropdown at the top and choose **Khapri · Durg**. Click site **1** in
*Suggested sites*, then **Design a pond here**. Wait for the panel.]

> This is the contour map our professor gave us, Khapri in Durg. At first, my app put the pond
> next to the big river here. That was wrong. The river comes from outside the map, so my
> program did not see how much water it carries. I fixed it: the app now also reads a water
> map from the same satellite data. Now the pond is on a small side stream. It is safe from
> the river, and its catchment is one hundred and three hectares.

> Are the answers right? My catchments match a well-known library, pysheds, within two to
> three percent, and forty-one tests check shapes with known answers, like a V-shaped valley.

### Scene 5 · 4:05–4:40 · Built for the four lab machines — *Tab 5, Swagger*

[Show Swagger; scroll past `/analyzeArea` and `/jobs/{id}`.]

> The system is a REST API; all routes are listed here. Big jobs run in the background, so
> the app never freezes, and if too many come it says "try later" instead of crashing. It runs
> on all four lab machines behind a load balancer. With twenty users at once, an area took
> about two seconds.

### Scene 6 · 4:40–4:50 · Close — *Tab 1, scroll to the footer*

> All the code, the report and every design decision are on GitHub. Thank you for watching.

[Stop recording.]

---

## Part 3 — After recording

1. **Trim** the start and end in QuickTime (*Edit → Trim*). Check the length is **under 5:00**.
2. **Export** 1080p (*File → Export As → 1080p*).
3. **Upload** to YouTube:
   - Title: *AI-based Village Pond Planning System — Demo (CSD Assignment 1, Rahul Raj, 12341680)*
   - Visibility: **Public** (the brief asks for a public link, not unlisted).
   - Description: the GitHub link, and the deployed URL `http://10.1.75.53:4272` (campus network).
4. Open the video in a private/incognito window to confirm anyone can watch it.
5. Send me the link. I'll put it into the report (`\videourl` in
   `docs/report/latex/main.tex`), rebuild the PDF, and add it to the README.

**If something goes wrong while recording:** keep going and re-record just that scene; join
the clips in iMovie. If the analysis is slow on the day, say "the server is fetching the
elevation data" and wait — it is honest and it is what is happening.
