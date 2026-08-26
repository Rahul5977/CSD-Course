import { useEffect, useState } from "react";
import { Mark } from "./ui";

const REPO = "https://github.com/Rahul5977/AI-BasedPondAnalysis";
const links = {
  app: "/app",
  api: "/docs",
  report: `${REPO}/blob/main/docs/report/REPORT.md`,
  install: `${REPO}#installation`,
  adr: `${REPO}/tree/main/docs/adr`,
  licences: `${REPO}/blob/main/docs/LICENSES.md`,
  validation: `${REPO}/blob/main/docs/report/REPORT.md#7-validation-and-results`,
};

/** Public landing page at `/`. Every claim here is something the app actually does. */
export default function Landing() {
  const [villages, setVillages] = useState<{ id: string; name: string }[] | null>(null);
  useEffect(() => {
    fetch("/api/v1/villages?limit=5").then((r) => (r.ok ? r.json() : null)).then((p) => setVillages(p?.items ?? [])).catch(() => setVillages([]));
  }, []);
  const sample = villages?.[0];
  return (
    <div className="landing">
      <div className="nav"><div className="wrap">
        <a className="brand" href="/"><Mark />Village Pond Planner</a>
        <nav aria-label="Sections"><a href="#how">How it works</a><a href="#get">What you get</a><a href="#method">Methodology</a><a href="#validation">Validation</a><a href={links.api}>API</a><a href={links.report}>Report</a></nav>
        <a className="btn btn-primary btn-sm" href={links.app}>Open the planner</a>
      </div></div>

      <main className="wrap">
        <section className="hero">
          <div>
            <div className="eyebrow">Village pond planning · terrain-first</div>
            <h1>From a contour map to a <em>costed pond</em> — with the reasoning shown.</h1>
            <p className="lede">Upload a KML/KMZ of a village. Get the terrain, the streams, ranked pond sites, the catchment of any point you click, 45 years of rainfall, runoff by three methods and a pond design with fill reliability. Every number carries its unit and an honest uncertainty band.</p>
            <div className="cta"><a className="btn btn-primary" href={links.app}>Open the planner</a>{sample && <a className="btn btn-secondary" href={`/app?village=${sample.id}`}>See {sample.name}, the sample village</a>}</div>
            <div className="trust"><span>Validated against an independent model</span><span>Nothing hard-coded to one map</span><span>Works offline after first load</span></div>
          </div>
          <div className="screen">
            <div className="frame"><img src="/landing/streams.jpg" alt="Modelled streams over satellite imagery of the sample village" width="1456" height="900" /></div>
            <div className="float qty"><span className="label">Catchment at the suggested site</span><span className="value">38.3<small>ha</small></span><span className="band"><b>±26 %</b> · D8 · snapped to the channel</span></div>
          </div>
        </section>
      </main>

      <div className="strip"><div className="wrap">
        <div className="qty"><span className="label">Rainfall record</span><span className="value">45<small>years</small></span><span className="band">ERA5-Land, daily</span></div>
        <div className="qty"><span className="label">Catchment vs pysheds</span><span className="value">2–3<small>%</small></span><span className="band">on the main outlets</span></div>
        <div className="qty"><span className="label">Runoff methods</span><span className="value">3</span><span className="band">SCS-CN · rational · Strange</span></div>
        <div className="qty"><span className="label">Map layers</span><span className="value">13</span><span className="band">all on one map</span></div>
        <div className="qty"><span className="label">Areas analysed here</span><span className="value">{villages ? villages.length : "…"}</span><span className="band">{villages?.length ? villages.map((v) => v.name).join(", ") : "upload the first one"}</span></div>
      </div></div>

      <div className="wrap">
        <section className="block" id="how">
          <h2>How it works</h2>
          <p className="sub">Four steps, each one visible on the map. The pipeline is the same for any contour map — the grid, the UTM zone and the source accuracy are derived from the file you upload.</p>
          <div className="steps">
            <div className="step"><span className="n">1</span><h3>Upload the contours</h3><p className="small">KML or KMZ. Elevation is read from the geometry, the attributes or the label — and decoy fields are rejected.</p></div>
            <div className="step"><span className="n">2</span><h3>Terrain and streams</h3><p className="small">A DEM is interpolated, depressions filled, flow routed cell by cell. The streams appear over satellite imagery so you can check them.</p></div>
            <div className="step"><span className="n">3</span><h3>Pick the site</h3><p className="small">Sites are ranked on four terrain criteria with published weights — or click anywhere for the catchment of that point.</p></div>
            <div className="step"><span className="n">4</span><h3>Design and decide</h3><p className="small">Rainfall, runoff, a cost-optimised depth, fill reliability, eligible land, then a recommendation with an audit trail and a PDF.</p></div>
          </div>
        </section>

        <section className="block" id="get">
          <h2>What you get</h2>
          <p className="sub">The eight things the assignment asks for, on one map, each with its uncertainty stated.</p>
          <div className="cards">
            <div className="card"><span className="fr">Satellite · contours</span><h3>The village, seen</h3><p className="small">Imagery, contours at 1–10 m, hillshade, slope, wetness, curvature — thirteen layers you can toggle.</p></div>
            <div className="card"><span className="fr">Catchment</span><h3>Click a point, get its catchment</h3><p className="small">Snapped to the nearest channel with the distance shown; area, longest flow path, relief, and a flag if the map edge cuts it.</p></div>
            <div className="card"><span className="fr">Rainfall</span><h3>45 years, in plain words</h3><p className="small">“In 3 of every 4 years, expect at least this much” — the 75 % dependable year, monsoon share, rainy days, the 25-year storm.</p></div>
            <div className="card"><span className="fr">Runoff</span><h3>A range, not a number</h3><p className="small">SCS-CN on the daily series, the rational method and Strange's table — with the spread between them reported.</p></div>
            <div className="card"><span className="fr">Pond design</span><h3>Depth chosen by cost</h3><p className="small">Dimensions, gross and live storage, a daily water balance, fill reliability, a spillway and a bill of quantities.</p></div>
            <div className="card"><span className="fr">Land · recommendation</span><h3>Where digging is allowed</h3><p className="small">Named constraints, a satellite water mask, ownership stated as unknown when it is — then draft → submitted → approved with an audit trail.</p></div>
          </div>
        </section>

        <section className="block" id="method">
          <h2>Nothing is a black box</h2>
          <p className="sub">Every step names its algorithm and its source. These are the ones that decide the numbers.</p>
          <div className="method">
            <div><b>Priority-Flood + ε</b><span>Depression filling and flat resolution (Barnes et al. 2014)</span></div>
            <div><b>D8 flow routing</b><span>Steepest descent over eight neighbours (O'Callaghan &amp; Mark 1984)</span></div>
            <div><b>Nearest-channel snap</b><span>Pour point moved ≤ 150 m to a cell draining ≥ 2 ha; distance shown</span></div>
            <div><b>AHP site ranking</b><span>Saaty pairwise weights, consistency ratio reported (0.004)</span></div>
            <div><b>Weibull 75 %</b><span>Dependable rainfall by plotting position, complete years only</span></div>
            <div><b>SCS-CN, daily</b><span>Curve number from WorldCover × SoilGrids, summed day by day (TR-55)</span></div>
            <div><b>NDWI + OpenCV</b><span>Sentinel-2 water mask: Otsu threshold, morphology, connected components</span></div>
            <div><b>Daily water balance</b><span>Inflow, evaporation, seepage, dead storage → fill reliability</span></div>
          </div>
        </section>

        <section className="block" id="validation">
          <div className="valid">
            <div>
              <h2>Validated, and honest about the rest</h2>
              <p className="sub">Golden tests with analytic answers, a second independent delineation model, and a sensitivity study on the one thing that matters most: where you click.</p>
              <table className="table">
                <thead><tr><th>Check</th><th>Method</th><th className="num">Result</th></tr></thead>
                <tbody>
                  <tr><td>Catchment area</td><td>vs pysheds, snapped outlets</td><td className="num">2.0 % · 3.4 %</td></tr>
                  <tr><td>Pour-point sensitivity</td><td>±3 cells, raw → snapped</td><td className="num">CV 212 % → 48 %</td></tr>
                  <tr><td>Water mask</td><td>NDWI vs WorldCover water class</td><td className="num">9.0 % vs 8.1 %</td></tr>
                  <tr><td>Runoff hand check</td><td>CN 80, 50 mm day</td><td className="num">13.8 mm exact</td></tr>
                  <tr><td>Load</td><td>50 users, 60 s</td><td className="num">p95 560 ms</td></tr>
                </tbody>
              </table>
              <p className="small"><a href={links.validation}>Full validation section in the report →</a></p>
            </div>
            <div className="limits">
              <h3>Planning-grade, not survey-grade</h3>
              <p className="small">The terrain comes from contours that came from ~30 m satellite elevation. Relief under about 5 m is not real, and storage figures carry ±20 % or more. Land ownership is never assumed. The three runoff methods can disagree by 2× — and the app shows you that instead of hiding it.</p>
              <p className="small">Use it to shortlist and size; confirm with a survey before you dig.</p>
            </div>
          </div>
        </section>
      </div>

      <div className="ctaband"><div className="wrap">
        <div><h2>Try it with the sample village</h2><p>{sample ? `${sample.name} — the provided contour map, already analysed.` : "Upload the provided contour map and watch it analysed in seconds."}</p></div>
        <div className="cta" style={{ margin: 0 }}><a className="btn btn-secondary" href={links.app}>Open the planner</a><a className="btn btn-ghost" style={{ color: "#fff" }} href={links.report}>Read the methodology →</a></div>
      </div></div>

      <footer className="foot"><div className="wrap">
        <div><div className="fbrand">Village Pond Planner</div><p>A 7th-semester project. Open source, built to be explained: every design decision is an ADR, every algorithm is cited.</p></div>
        <div><h3>Use</h3><a href={links.app}>Open the planner</a><a href={links.api}>API documentation</a><a href={links.install}>Installation guide</a></div>
        <div><h3>Read</h3><a href={links.report}>Technical report</a><a href={links.adr}>Decision records</a><a href={links.validation}>Validation</a></div>
        <div><h3>Data</h3><a href={links.licences}>Licences &amp; attribution</a><a href={REPO}>GitHub repository</a></div>
      </div></footer>
    </div>
  );
}
