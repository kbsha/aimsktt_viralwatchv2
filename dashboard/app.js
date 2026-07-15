/* ViralWatch dashboard — talks to the FastAPI service on the same origin. */

const API = ""; // same origin. If you split the frontend onto its own host,
                // set this to e.g. "https://viralwatch.onrender.com".

// risk ramp — must match style.css --r0..--r4
function colorFor(score) {
  if (score >= 0.8) return "#e63946";
  if (score >= 0.6) return "#f4a261";
  if (score >= 0.4) return "#e9c46a";
  if (score >= 0.2) return "#8ab17d";
  return "#2a9d8f";
}

const map = L.map("map", { zoomControl: true, attributionControl: true })
  .setView([-1.9, 29.1], 8); // centred on the Kivu / Rwanda border

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

const layersByZone = {};   // zone -> leaflet layer
const rowsByZone = {};     // zone -> table <tr>

/* ---------- load everything ---------- */
Promise.all([
  fetch(`${API}/geojson`).then((r) => r.json()),
  fetch(`${API}/earlywarning`).then((r) => r.json()),
  fetch(`${API}/briefing`).then((r) => r.json()),
])
  .then(([geo, ew, brief]) => {
    drawMap(geo);
    drawWatchlist(ew);
    drawBriefing(brief);
  })
  .catch((err) => {
    document.getElementById("briefing-text").textContent =
      "Could not reach the API. Is the server running? (uvicorn app.main:app)";
    console.error(err);
  });

/* ---------- map choropleth ---------- */
function drawMap(geo) {
  const layer = L.geoJSON(geo, {
    style: (f) => ({
      fillColor: colorFor(f.properties.warning_score ?? 0),
      weight: f.properties.borders_rwanda ? 2.5 : 1,
      color: f.properties.borders_rwanda ? "#4cc9f0" : "#3a4956",
      fillOpacity: 0.72,
    }),
    onEachFeature: (f, lyr) => {
      const z = f.properties.zone;
      layersByZone[z] = lyr;
      lyr.bindTooltip(
        `${z} · score ${(f.properties.warning_score ?? 0).toFixed(2)}`,
        { sticky: true }
      );
      lyr.on("mouseover", () => lyr.setStyle({ fillOpacity: 0.92 }));
      lyr.on("mouseout", () => lyr.setStyle({ fillOpacity: 0.72 }));
      lyr.on("click", () => selectZone(z));
    },
  }).addTo(map);
  try { map.fitBounds(layer.getBounds().pad(0.15)); } catch (e) {}
}

/* ---------- watchlist table ---------- */
function drawWatchlist(ew) {
  document.getElementById("zone-count").textContent =
    `${ew.n_zones} zones · updated ${ew.generated_at}`;
  const body = document.getElementById("watchlist-body");
  body.innerHTML = "";
  ew.watchlist.forEach((z) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="zcell">${z.zone}${
        z.borders_rwanda ? '<span class="rw-tag">RW</span>' : ""
      }</span></td>
      <td>${z.province}</td>
      <td class="num"><span class="score-chip" style="background:${colorFor(
        z.warning_score
      )}">${z.warning_score.toFixed(2)}</span></td>
      <td class="num">${z.new_cases_last7}</td>`;
    tr.addEventListener("click", () => selectZone(z.zone));
    rowsByZone[z.zone] = tr;
    body.appendChild(tr);
  });
}

/* ---------- briefing panel + header stats ---------- */
function drawBriefing(b) {
  document.getElementById("briefing-text").textContent = b.summary || "—";
  const set = (id, v) => (document.getElementById(id).textContent = v ?? "—");
  set("stat-cases", b.total_cases != null ? b.total_cases.toLocaleString() : "—");
  set("stat-deaths", b.total_deaths != null ? b.total_deaths.toLocaleString() : "—");
  set("stat-cfr", b.case_fatality_ratio != null ? b.case_fatality_ratio + "%" : "—");
  set("stat-date", b.source || "—");

  const flags = document.getElementById("briefing-flags");
  flags.innerHTML = "";
  (b.severity_flags || []).forEach((f) => addFlag(flags, f, false));
  (b.cross_border_mentions || []).forEach((f) => addFlag(flags, f, true));
}
function addFlag(container, text, isBorder) {
  const s = document.createElement("span");
  s.className = "flag" + (isBorder ? " border" : "");
  s.textContent = text;
  container.appendChild(s);
}

/* ---------- zone selection -> /predict ---------- */
function selectZone(zone) {
  Object.values(rowsByZone).forEach((tr) => tr.classList.remove("active"));
  if (rowsByZone[zone]) {
    rowsByZone[zone].classList.add("active");
    rowsByZone[zone].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  const lyr = layersByZone[zone];
  if (lyr) { try { map.fitBounds(lyr.getBounds().pad(2)); } catch (e) {} }

  fetch(`${API}/predict/${encodeURIComponent(zone)}`)
    .then((r) => r.json())
    .then((p) => {
      showDetail(p);
      if (lyr) {
        lyr.bindPopup(
          `<b>${p.zone}</b><br>Next-7-day case probability: ` +
          `<b style="color:${colorFor(p.next7d_case_probability)}">` +
          `${(p.next7d_case_probability * 100).toFixed(0)}%</b>`
        ).openPopup();
      }
    })
    .catch((e) => console.error(e));
}

function showDetail(p) {
  const box = document.getElementById("detail");
  box.hidden = false;
  document.getElementById("detail-zone").textContent =
    `${p.zone} — ${p.province}${p.borders_rwanda ? " · borders Rwanda" : ""}`;
  const pct = (p.next7d_case_probability * 100).toFixed(0);
  document.getElementById("detail-grid").innerHTML = `
    <div class="dm prob-big"><span class="dm-val" style="color:${colorFor(
      p.next7d_case_probability
    )}">${pct}%</span><span class="dm-lbl">next-7-day case probability</span></div>
    <div class="dm"><span class="dm-val">${p.cumulative_cases}</span><span class="dm-lbl">cumulative cases</span></div>
    <div class="dm"><span class="dm-val">${p.days_since_first_case}</span><span class="dm-lbl">days since first case</span></div>
    <div class="dm"><span class="dm-val">${p.travel_time_min}m</span><span class="dm-lbl">travel to treatment</span></div>
    <div class="dm"><span class="dm-val">${p.population_density}</span><span class="dm-lbl">pop density /km²</span></div>`;
}

document.getElementById("detail-close").addEventListener("click", () => {
  document.getElementById("detail").hidden = true;
  Object.values(rowsByZone).forEach((tr) => tr.classList.remove("active"));
});
