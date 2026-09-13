async function load() {
  const el = document.getElementById("tidy-status");
  const table = document.getElementById("tidy-table");
  try {
    const r = await fetch("data/tidy3d_compare.json");
    const j = await r.json();
    if (j.missing) {
      el.textContent =
        "Tidy3D batch not on disk yet. Full batch writes analysis/results/tidy3d_compare.json.";
      return;
    }
    const notes = j.notes || {};
    const aligned = j.best_offset_um
      ? " Fiber x-offset maximised at 1550.00 nm."
      : " First-batch file: beam at grating midpoint.";
    el.textContent =
      "Tidy3D loaded. IL below is at 1550.00 nm." +
      aligned +
      (notes.wg_continuation ? " " + notes.wg_continuation + "." : "");
    const jobs = j.jobs || {};
    const rows = [];
    for (const [name, job] of Object.entries(jobs)) {
      if (job.kind && job.kind !== "nominal") continue;
      const il = Number(job.il_1550_db);
      const lam = job.lambda_reported_nm;
      const off =
        job.x_fib_offset_um === undefined ? "" : ` · x_fib ${Number(job.x_fib_offset_um).toFixed(1)} µm`;
      rows.push(
        `<tr><td>${job.design || name}</td><td class="num">${il.toFixed(2)} dB</td><td>λ = ${lam} nm · ${name}${off}</td></tr>`
      );
    }
    const etch = Object.entries(jobs).filter(([, job]) => job.kind === "etch");
    if (etch.length) {
      const designs = new Set(etch.map(([, job]) => job.design));
      const fillNote = designs.has("taillaert")
        ? "includes fill-only"
        : "fill-only missing — uniqueness claim not allowed";
      rows.push(`<tr><td colspan="3">Etch sweep at 1550.00 nm (${fillNote})</td></tr>`);
      for (const [name, job] of etch) {
        rows.push(
          `<tr><td>${job.design} @ ${job.etch_nm} nm etch</td><td class="num">${Number(job.il_1550_db).toFixed(2)} dB</td><td>${name}</td></tr>`
        );
      }
      const by = {};
      for (const job of Object.values(jobs)) {
        if (!job.design || job.il_1550_db === undefined) continue;
        if (job.kind !== "nominal" && job.kind !== "etch") continue;
        const k = job.design;
        by[k] = by[k] || [];
        by[k].push(Number(job.il_1550_db));
      }
      rows.push(`<tr><td colspan="3">Worst IL among listed etch/nominal jobs</td></tr>`);
      for (const [k, arr] of Object.entries(by)) {
        const w = Math.max(...arr);
        rows.push(`<tr><td>${k} worst-case</td><td class="num">${w.toFixed(2)} dB</td><td>max of ${arr.length} samples</td></tr>`);
      }
    }
    table.innerHTML = rows.join("") || `<tr><td colspan="3">No nominal jobs in file.</td></tr>`;
  } catch (e) {
    el.textContent = "Could not read Tidy3D results: " + e;
  }
}
load();
