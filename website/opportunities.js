/* Public records are read-only. No visitor analytics or personal data collection. */
(function () {
  "use strict";

  var state = { records: [], lane: "all", city: "all", query: "", sort: "recent", loaded: false };
  var byId = function (id) { return document.getElementById(id); };

  function torontoToday() {
    // Date boundaries follow the business's Ontario calendar, not UTC.
    var bits = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Toronto", year: "numeric", month: "2-digit", day: "2-digit"
    }).formatToParts(new Date());
    var part = function (name) {
      var value = bits.filter(function (item) { return item.type === name; })[0];
      return value ? value.value : "";
    };
    return part("year") + "-" + part("month") + "-" + part("day");
  }
  function dayNumber(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) return NaN;
    var value = Date.parse(date + "T00:00:00Z");
    return Number.isFinite(value) ? Math.floor(value / 86400000) : NaN;
  }
  function pretty(date, short) {
    var parts = (date || "").split("-");
    if (parts.length !== 3) return "Date unavailable";
    var val = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
    if (isNaN(val.getTime())) return "Date unavailable";
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "UTC", month: "short", day: "numeric",
      year: short ? undefined : "numeric"
    }).format(val);
  }
  function validUrl(raw) {
    try {
      var url = new URL(raw);
      return url.protocol === "https:" && !!url.hostname &&
        !url.username && !url.password && raw.length < 1600;
    } catch (_) { return false; }
  }
  function textEl(tag, cls, text) {
    var element = document.createElement(tag);
    if (cls) element.className = cls;
    element.textContent = text == null ? "" : String(text);
    return element;
  }
  function current(record, today) {
    var n = dayNumber(record.source_date);
    var delta = dayNumber(today) - n;
    return Number.isFinite(delta) && delta >= 0 && delta <= 4;
  }
  function normalized(record, today) {
    if (!record || typeof record !== "object") return null;
    if (record.approved_for_publication !== true || record.rights_checked !== true ||
        record.source_checked !== true) return null;
    if (!current(record, today) || !validUrl(record.source_url)) return null;
    if (record.lane !== "industrial_equipment" && record.lane !== "commercial_development") return null;
    if (typeof record.city !== "string" || !record.city.trim() ||
        typeof record.title !== "string" || !record.title.trim() ||
        typeof record.scope !== "string" || !record.scope.trim()) return null;
    return record;
  }
  function showWindow(today) {
    var end = dayNumber(today);
    var begin = new Date((end - 4) * 86400000).toISOString().slice(0, 10);
    byId("window-label").textContent = pretty(begin, true) + " — " + pretty(today, false);
  }
  function makeCard(rec) {
    var card = textEl("article", "op-card " + rec.lane, "");
    var top = textEl("div", "op-card-top", "");
    var laneName = rec.lane === "industrial_equipment" ? "Industrial & equipment" : "Commercial development";
    top.appendChild(textEl("span", "op-card-lane " + rec.lane, laneName));
    top.appendChild(textEl("span", "op-card-date", pretty(rec.source_date, false)));
    card.appendChild(top);

    var body = textEl("div", "op-card-content", "");
    body.appendChild(textEl("div", "op-card-city", rec.city));
    body.appendChild(textEl("h3", "", rec.title));
    body.appendChild(textEl("p", "op-card-scope", rec.scope));
    var tags = textEl("div", "op-card-tags", "");
    tags.appendChild(textEl("span", "", "Research candidate"));
    if (rec.stage) tags.appendChild(textEl("span", "", String(rec.stage).slice(0, 65)));
    if (rec.first_publication_verified !== true) {
      tags.appendChild(textEl("span", "unverified", "First publication unverified"));
    }
    if (rec.open_supplier_package_verified !== true) {
      tags.appendChild(textEl("span", "unverified", "Supplier availability unknown"));
    }
    body.appendChild(tags);
    var additional = "Source date basis: " + (rec.date_basis || "Unspecified source date");
    if (rec.company) additional += " · Organization mentioned: " + rec.company;
    body.appendChild(textEl("p", "op-card-more", additional));
    card.appendChild(body);

    var bottom = textEl("div", "op-card-bottom", "");
    var link = textEl("a", "", "Inspect original source ↗");
    link.href = rec.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", "Inspect original source for " + rec.title);
    bottom.appendChild(link);
    bottom.appendChild(textEl("span", "op-card-id", rec.source_project_id || "Research record"));
    card.appendChild(bottom);
    return card;
  }
  function setEmpty(empty, filtered) {
    byId("op-empty").hidden = !empty;
    if (!empty) return;
    byId("op-empty-title").textContent = filtered ?
      "Nothing matches those filters" : "No approved public records in this five-day window";
    byId("op-empty-description").textContent = filtered ?
      "Try changing the municipality, category or search terms. The underlying public feed may have fewer reviewed records than the private research queue." :
      "Only manually approved, source-checked records are published. A quiet or unpublished day is not evidence that no projects exist.";
  }
  function render() {
    if (!state.loaded) return;
    var count = state.records.length;
    var term = state.query.trim().toLocaleLowerCase();
    var filtered = state.records.filter(function (rec) {
      if (state.lane !== "all" && state.lane !== rec.lane) return false;
      if (state.city !== "all" && state.city !== rec.city) return false;
      if (!term) return true;
      return [rec.title, rec.scope, rec.city, rec.company,
        rec.source_project_id, rec.stage].join(" ").toLocaleLowerCase().includes(term);
    });
    filtered.sort(function (a, b) {
      if (state.sort === "city") {
        return a.city.localeCompare(b.city) || b.source_date.localeCompare(a.source_date);
      }
      return b.source_date.localeCompare(a.source_date) || a.city.localeCompare(b.city);
    });
    var target = byId("op-results");
    target.replaceChildren();
    var fragment = document.createDocumentFragment();
    filtered.forEach(function (rec) { fragment.appendChild(makeCard(rec)); });
    target.appendChild(fragment);
    target.setAttribute("aria-busy", "false");
    var filteredMode = state.lane !== "all" || state.city !== "all" || !!term;
    setEmpty(filtered.length === 0, count > 0 && filteredMode);
    byId("op-result-count").textContent = filtered.length + " of " + count + " approved records shown";
  }
  function initialize(records, published, today) {
    state.records = records;
    state.loaded = true;
    byId("metric-total").textContent = String(records.length);
    byId("metric-industrial").textContent = String(records.filter(function (r) { return r.lane === "industrial_equipment"; }).length);
    byId("metric-commercial").textContent = String(records.filter(function (r) { return r.lane === "commercial_development"; }).length);
    var cities = Array.from(new Set(records.map(function (r) { return r.city; }))).sort();
    byId("metric-cities").textContent = String(cities.length);
    byId("tab-all-count").textContent = String(records.length);
    var select = byId("op-city");
    cities.forEach(function (city) {
      var opt = document.createElement("option");
      opt.value = city;
      opt.textContent = city;
      select.appendChild(opt);
    });
    byId("publication-status").textContent = published ?
      "Editorial update: " + pretty(published, false) : "Awaiting first approved briefing";
    render();
  }

  var today = torontoToday();
  showWindow(today);
  byId("year").textContent = String(new Date().getFullYear());

  document.querySelectorAll(".op-tab").forEach(function (button) {
    button.addEventListener("click", function () {
      state.lane = button.dataset.lane;
      document.querySelectorAll(".op-tab").forEach(function (other) {
        var active = other === button;
        other.classList.toggle("active", active);
        other.setAttribute("aria-pressed", String(active));
      });
      render();
    });
  });
  byId("op-search-input").addEventListener("input", function (e) {
    state.query = e.target.value;
    render();
  });
  byId("op-city").addEventListener("change", function (e) {
    state.city = e.target.value;
    render();
  });
  byId("op-sort").addEventListener("change", function (e) {
    state.sort = e.target.value;
    render();
  });
  byId("op-clear").addEventListener("click", function () {
    state.lane = "all"; state.city = "all"; state.query = ""; state.sort = "recent";
    byId("op-search-input").value = "";
    byId("op-city").value = "all";
    byId("op-sort").value = "recent";
    document.querySelectorAll(".op-tab").forEach(function (button) {
      var active = button.dataset.lane === "all";
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    render();
  });

  fetch("./data/opportunities.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw Error("Publication file unavailable");
      return response.json();
    })
    .then(function (payload) {
      var list = Array.isArray(payload.records) ? payload.records : [];
      var seen = new Set();
      var items = list.map(function (r) { return normalized(r, today); })
        .filter(Boolean).filter(function (r) {
          var id = String(r.id || r.lane + ":" + r.city + ":" + r.source_project_id);
          if (seen.has(id)) return false;
          seen.add(id);
          return true;
        });
      initialize(items, payload.published_on || "", today);
    })
    .catch(function () {
      initialize([], "", today);
      byId("publication-status").textContent = "No public briefing available";
    });
})();
