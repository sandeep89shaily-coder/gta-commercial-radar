/* Local publisher: reads selected CSV files, never uploads or submits data. */
(function () {
  "use strict";
  var rows = [];
  var byId = function (id) { return document.getElementById(id); };
  var message = function (text) { byId("pub-status").textContent = text; };
  function todayInOntario() {
    var pieces = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Toronto", year: "numeric", month: "2-digit", day: "2-digit"
    }).formatToParts(new Date());
    function part(key) { var found = pieces.filter(function (p) { return p.type === key; })[0]; return found ? found.value : ""; }
    return part("year") + "-" + part("month") + "-" + part("day");
  }
  byId("pub-date").value = todayInOntario();

  function dayNumber(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) return NaN;
    var value = Date.parse(date + "T00:00:00Z");
    return Number.isFinite(value) ? Math.floor(value / 86400000) : NaN;
  }
  function withinFiveDays(date, issueDate) {
    var age = dayNumber(issueDate) - dayNumber(date);
    return Number.isFinite(age) && age >= 0 && age <= 4;
  }
  function validUrl(raw) {
    try {
      var obj = new URL(raw);
      return obj.protocol === "https:" && !!obj.hostname &&
        !obj.username && !obj.password && !obj.hash && raw.length < 1500;
    } catch (_) { return false; }
  }
  function csvRows(raw) {
    // RFC-4180-style quoted fields, including embedded commas and newlines.
    // Parser returns only data; content is never inserted as HTML.
    var table = [], line = [], field = "", quoted = false;
    raw = String(raw || "").replace(/^\uFEFF/, "");
    for (var i = 0; i < raw.length; i++) {
      var c = raw.charAt(i);
      if (quoted) {
        if (c === '"' && raw.charAt(i + 1) === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"' && field === "") quoted = true;
      else if (c === ",") { line.push(field); field = ""; }
      else if (c === "\r" || c === "\n") {
        if (c === "\r" && raw.charAt(i + 1) === "\n") i++;
        line.push(field); field = "";
        if (line.some(function (item) { return item !== ""; })) table.push(line);
        line = [];
      } else field += c;
    }
    if (quoted) throw Error("Unterminated quoted CSV field");
    if (field !== "" || line.length) {
      line.push(field);
      table.push(line);
    }
    var header = (table.shift() || []).map(function (h) { return h.trim(); });
    if (header.indexOf("source_event_date") < 0 ||
        header.indexOf("source_url") < 0 ||
        header.indexOf("scope") < 0) {
      throw Error("This is not a GTA Radar five-day research CSV.");
    }
    return table.map(function (cells) {
      var result = {};
      header.forEach(function (h, idx) { result[h] = cells[idx] || ""; });
      return result;
    });
  }
  function safeStr(value, max) { return String(value || "").replace(/\s+/g, " ").trim().slice(0, max); }
  function statusReason(record, issueDate) {
    if (!withinFiveDays(record.source_event_date, issueDate)) return "Outside five-day source-event window";
    if (!validUrl(record.source_url)) return "Missing direct HTTPS source";
    if (!record.city || !record.project_or_company || safeStr(record.scope, 2000).length < 30) return "Incomplete project identity or scope";
    if (/COMPLETED|AWARDED|INACTIVE|CANCELLED|WITHDRAWN|OPERATIONAL/i.test(
          String(record.stage || "") + " " + String(record.decision || ""))) {
      return "Completed, awarded or inactive — not a fresh prospect";
    }
    return "";
  }
  function niceRow(row, lane) {
    var id = lane + ":" + row.city + ":" + (row.source_project_id || row.source_url);
    return {
      id: id.slice(0, 420),
      lane: lane,
      title: safeStr(row.project_or_company, 180),
      city: safeStr(row.city, 90),
      address: safeStr(row.address_or_company_site_unverified, 210),
      scope: safeStr(row.scope, 1050),
      source_date: safeStr(row.source_event_date, 10),
      date_basis: safeStr(row.source_event_date_basis, 130),
      first_seen: safeStr(row.radar_first_observed, 10),
      observation: safeStr(row.observation, 70),
      stage: safeStr(row.stage, 110),
      source_url: String(row.source_url || "").trim(),
      source_project_id: safeStr(row.source_project_id, 190),
      company: lane === "industrial_equipment" ? safeStr(row.company_source_claim, 150) : "",
      first_publication_verified: false,
      buyer_verified: false,
      open_supplier_package_verified: false,
      approved_for_publication: true,
      rights_checked: true,
      source_checked: true
    };
  }
  function divWith(cls, text) {
    var el = document.createElement("div");
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function countSelected() {
    return rows.filter(function (r) { return r.checked && !r.hold; }).length;
  }
  function update() {
    var reviewed = rows.filter(function (r) { return !r.hold; }).length;
    var held = rows.length - reviewed;
    byId("pub-counts").textContent = countSelected() + " selected · " + reviewed + " eligible · " + held + " held";
    byId("pub-export").disabled = !countSelected() || !byId("pub-confirm").checked;
  }
  function drawRows() {
    var destination = byId("pub-rows");
    destination.replaceChildren();
    var fragment = document.createDocumentFragment();
    rows.forEach(function (item) {
      var row = divWith("pub-row" + (item.hold ? " held" : ""));
      var check = document.createElement("input");
      check.type = "checkbox";
      check.checked = item.checked;
      check.disabled = !!item.hold;
      check.setAttribute("aria-label", "Approve " + item.data.project_or_company);
      check.addEventListener("change", function () { item.checked = check.checked; update(); });
      row.appendChild(check);
      var info = divWith("");
      var title = document.createElement("strong");
      title.textContent = item.data.project_or_company || "Unnamed record";
      info.appendChild(title);
      info.appendChild(divWith("detail", item.data.city + " · " + item.data.source_event_date + " · " + safeStr(item.data.scope, 185)));
      if (validUrl(item.data.source_url)) {
        var link = document.createElement("a");
        link.className = "pub-source";
        link.href = item.data.source_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Inspect official/source record ↗";
        info.appendChild(link);
      }
      row.appendChild(info);
      var meta = divWith("pub-meta");
      var lane = document.createElement("b");
      lane.textContent = item.lane === "industrial_equipment" ? "Equipment" : "Commercial";
      meta.appendChild(lane);
      meta.appendChild(divWith("", item.hold || "Requires individual review"));
      row.appendChild(meta);
      fragment.appendChild(row);
    });
    if (!rows.length) fragment.appendChild(divWith("pub-row", "No candidate records in these CSVs."));
    destination.appendChild(fragment);
    update();
  }
  byId("pub-load").addEventListener("click", async function () {
    var tasks = [
      [byId("pub-general").files[0], "commercial_development"],
      [byId("pub-equipment").files[0], "industrial_equipment"]
    ].filter(function (part) { return !!part[0]; });
    if (!tasks.length) { message("Choose at least one official Radar five-day research CSV."); return; }
    var issueDate = byId("pub-date").value;
    if (!Number.isFinite(dayNumber(issueDate))) { message("Select a valid Ontario issue date."); return; }
    byId("pub-confirm").checked = false;
    byId("pub-export").disabled = true;
    rows = [];
    try {
      for (var n = 0; n < tasks.length; n++) {
        var file = tasks[n][0], lane = tasks[n][1];
        if (file.size > 8_000_000) throw Error(file.name + " is too large for this local tool.");
        var raw = csvRows(await file.text());
        if (rows.length + raw.length > 5000) throw Error("Too many records. Limit is 5,000.");
        raw.forEach(function (item) {
          rows.push({ data: item, lane: lane, checked: false,
            hold: statusReason(item, issueDate) });
        });
      }
      drawRows();
      message("Files read locally. " + rows.length + " records inspected. Select only the sources you checked; none are approved automatically.");
    } catch (err) {
      rows = [];
      drawRows();
      message("Import held: " + (err && err.message ? err.message : "Unable to read CSV."));
    }
  });
  byId("pub-select-none").addEventListener("click", function () {
    rows.forEach(function (r) { r.checked = false; });
    byId("pub-confirm").checked = false;
    drawRows();
    message("All approvals cleared.");
  });
  byId("pub-confirm").addEventListener("change", update);
  byId("pub-export").addEventListener("click", function () {
    if (!byId("pub-confirm").checked) { message("Confirm individual source and reuse review first."); return; }
    var selected = rows.filter(function (r) { return r.checked && !r.hold; });
    if (!selected.length) { message("No records are selected for publication."); return; }
    var issueDate = byId("pub-date").value;
    var records = [], seen = new Set();
    selected.forEach(function (item) {
      var result = niceRow(item.data, item.lane);
      if (!withinFiveDays(result.source_date, issueDate) || !validUrl(result.source_url)) return;
      if (seen.has(result.id)) return;
      seen.add(result.id);
      records.push(result);
    });
    if (!records.length) { message("Publication held: no valid source-checked records."); return; }
    var payload = {
      schema_version: 1, published_on: issueDate, window_days: 5,
      records: records
    };
    var blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "opportunities.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    message("Downloaded " + records.length + " editorially approved research record(s). Replace website/data/opportunities.json in GitHub, commit, then manually deploy Pages. Nothing has been published yet.");
  });
})();
