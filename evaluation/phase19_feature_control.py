#!/usr/bin/env python3
"""
phase19_feature_control.py   (v3)

CONTROL F — is the cross-climate gap produced by the common feature set?

THE OBJECTION
Every model in this paper sees only lagged capacity-normalized power plus
cyclical time encodings. Under that feature set a model can encode little
except the source climate's own autocorrelation and diurnal statistics, so a
transferred model may fail *by construction* rather than because climates
differ. The five controls in Section 4.6 vary sampling interval, site count,
baseline strength, site novelty and installation class. None varies the feature
set. This script does.

Irradiance is the physically general driver: the same quantity in a desert and
in a subtropical city, and carried by DKASC, HKUST and PVDAQ. Ausgrid is absent
because it publishes no weather at all.

THREE CONDITIONS

  1. common          all protocol rows, 8 base features.
                     Exists to reproduce Phase 13 and gate the run.

  2. common_cc       complete-case rows only (irradiance present), base
                     features. The honest comparator for 3.

  3. common+irr_cc   the same complete-case rows, base features plus
                     irradiance at the target timestamp.

2 and 3 are trained and scored on IDENTICAL rows at IDENTICAL sites and differ
by exactly one column. No NaN ever reaches the model in either, so a difference
between them cannot be attributed to missing-value handling.

WHY THE COMPLETE-CASE PAIR EXISTS
v2 fed irradiance as NaN where absent. Coverage is 98% on DKASC, 71% on HKUST
and 60% on PVDAQ, and HistGradientBoostingRegressor learns a default direction
for NaN from its training data. A model trained on DKASC, which is almost fully
observed, meets PVDAQ with 40% missing and applies an arbitrary default. The
transfer collapse v2 reported (gap 0.021 -> 0.325) is therefore confounded with
differential missingness. Conditions 2 and 3 remove that confound entirely.
Site-level coverage filtering was considered and rejected: at a 90% threshold
PVDAQ retains 2 sites, too few to be a transfer target.

WHY LAGS ARE BUILT BEFORE MASKING
v1 dropped rows with no irradiance before building features, which meant
pn[idx-1] was no longer the previous 15-minute step but whatever row survived,
sometimes days earlier. Both the model and the persistence baseline were then
computed on non-contiguous history and every skill score was meaningless.
Here every feature, and the persistence reference, is built on the full
contiguous series first. The complete-case mask is applied only afterwards, to
select which rows are used. Do not move the mask earlier.

VALIDATION GATE
`common` must reproduce Phase 13's baseline_15min in-climate skill for these
three archives and score 1 / 37 / 7 sites. On failure the script writes the CSV
and exits without printing a verdict.

COMPARATOR
Not the 0.109 four-archive baseline of Table 12. Ausgrid, the weakest source,
is excluded here, so the reference is whatever `common_cc` produces on this
subset. Report the pair, never the percentage change alone.

Everything else matches Phase 13: gradient boosting, same hyperparameters,
per-site capacity normalization, fixed chronological splits, 100,000-example
training cap, 2,000 test rows per site, seeds 42/7/123.

Writes  phase19_feature_control_results.csv
        phase19_summary.txt

Run:  python phase19_feature_control.py
"""

import os
import sys
import time

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import HistGradientBoostingRegressor
except ImportError:
    sys.exit("scikit-learn required:  pip install scikit-learn")

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.abspath(os.path.join(HERE, "..", "protocol"))

FILES = [
    ("DKASC", "dataset1_DKASC_15min_labeled.csv"),
    ("HKUST", "dataset2_HKUST_15min_labeled.csv"),
    ("PVDAQ", "dataset4_PVDAQ_15min_labeled.csv"),
]
CLIM = [c for c, _ in FILES]

N_LAGS = 4
SEEDS = [42, 7, 123]
MAX_TRAIN = 100_000
MAX_TEST_PER_SITE = 2_000
RNG = 0
GBM = dict(max_iter=400, learning_rate=0.06, early_stopping=True,
           validation_fraction=0.15, n_iter_no_change=25)

USECOLS = ["Timestamp", "Power_kW", "Irradiance_Wm2", "Site_ID", "Split", "IsRareEvent"]

EXPECTED_DIAG = {"DKASC": 0.127, "HKUST": 0.058, "PVDAQ": 0.036}
EXPECTED_SITES = {"DKASC": 1, "HKUST": 37, "PVDAQ": 7}
GATE_TOL = 0.030

# (feature key, complete-case?, label)
CONDITIONS = [
    ("base", False, "common"),
    ("base", True,  "common_cc"),
    ("wide", True,  "common+irr_cc"),
]


def load(tag, fname):
    """Per-site arrays over the FULL protocol row set. Features and the
    persistence reference are built on the contiguous series; the complete-case
    mask is carried alongside and applied later, never here."""
    path = os.path.join(PROTO, fname)
    if not os.path.exists(path):
        sys.exit(f"missing input file: {path}")
    df = pd.read_csv(path, usecols=USECOLS, dtype={"Site_ID": str}, low_memory=False)
    df["Site_ID"] = df["Site_ID"].str.replace("^ID_", "", regex=True)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    if df["IsRareEvent"].dtype != bool:
        df["IsRareEvent"] = df["IsRareEvent"].astype(bool)

    sites, cov = [], []
    for site, g in df.groupby("Site_ID", sort=False):
        g = g.sort_values("Timestamp")
        p = g["Power_kW"].to_numpy(dtype=float)
        n = len(p)
        if n <= N_LAGS + 2:
            continue
        pos = p[p > 0]
        cap = np.percentile(pos, 99.5) if pos.size else np.nan
        if not np.isfinite(cap) or cap <= 0:
            continue
        pn = p / cap
        ts = g["Timestamp"]
        hf = ts.dt.hour.to_numpy() + ts.dt.minute.to_numpy() / 60.0
        doy = ts.dt.dayofyear.to_numpy()
        tf = np.column_stack([np.sin(2*np.pi*hf/24), np.cos(2*np.pi*hf/24),
                              np.sin(2*np.pi*doy/365.25), np.cos(2*np.pi*doy/365.25)])
        irr = g["Irradiance_Wm2"].to_numpy(dtype=float)

        idx = np.arange(N_LAGS, n)                       # contiguous; lags intact
        lags = np.column_stack([pn[idx - k] for k in range(1, N_LAGS + 1)])
        base = np.column_stack([lags, tf[idx]])
        wide = np.column_stack([base, irr[idx]])
        has_irr = np.isfinite(irr[idx])

        cov.append(has_irr.mean())
        sites.append(dict(
            tag=tag, site=str(site), cap=cap,
            base=base, wide=wide, has_irr=has_irr,
            y=pn[idx], naive=pn[idx - 1],
            split=g["Split"].to_numpy()[idx],
            rare=g["IsRareEvent"].to_numpy()[idx].astype(bool)))
    print(f"  {tag:<7} sites {len(sites):3d} | mean irradiance coverage "
          f"{100*np.mean(cov):.1f}% | no rows dropped at load", flush=True)
    return sites


def assemble(sites, featkey, complete_case, rng):
    """Row mask uses the base features plus, when complete_case, the presence of
    irradiance. It never depends on the irradiance VALUE, so conditions 2 and 3
    select exactly the same rows."""
    tr_X, tr_y = [], []
    te = dict(X=[], y=[], naive=[], cap=[], site=[], rare=[])
    for s in sites:
        ok = np.isfinite(s["base"]).all(axis=1) & np.isfinite(s["y"]) & np.isfinite(s["naive"])
        if complete_case:
            ok = ok & s["has_irr"]
        i_tr = np.flatnonzero((s["split"] == "train") & ok)
        i_te = np.flatnonzero((s["split"] == "test") & ok)
        if i_tr.size:
            tr_X.append(s[featkey][i_tr]); tr_y.append(s["y"][i_tr])
        if i_te.size:
            if i_te.size > MAX_TEST_PER_SITE:
                i_te = np.sort(rng.choice(i_te, MAX_TEST_PER_SITE, replace=False))
            te["X"].append(s[featkey][i_te]);  te["y"].append(s["y"][i_te])
            te["naive"].append(s["naive"][i_te])
            te["cap"].append(np.full(i_te.size, s["cap"]))
            te["site"].append(np.full(i_te.size, s["site"], dtype=object))
            te["rare"].append(s["rare"][i_te])
    if not tr_X or not te["X"]:
        return None, None
    return (np.vstack(tr_X), np.concatenate(tr_y)), \
           {k: np.concatenate(v) for k, v in te.items()}


def rmse_by_site(y, yhat, cap, site):
    out = {}
    for s in np.unique(site):
        m = site == s
        if m.sum() < 2:
            continue
        e = (y[m] - yhat[m]) * cap[m]
        out[s] = float(np.sqrt(np.nanmean(e ** 2)))
    return out


def pooled(g, label):
    d = g[g.Features == label].copy()
    d["cond"] = np.where(d.Source == d.Target, "same", "tr")
    ov = (d.groupby(["cond", "Seed"]).Skill.mean().reset_index()
            .groupby("cond").Skill.mean())
    return float(ov["same"]), float(ov["tr"]), float(ov["same"] - ov["tr"])


def gate(res):
    fail = []
    g = res[(res.Model == "GBM") & (res.Features == "common")]
    n_sites = g[g.Source == g.Target].groupby("Target").Site_ID.nunique().to_dict()
    for t, want in EXPECTED_SITES.items():
        got = n_sites.get(t, 0)
        if got != want:
            fail.append(f"site count {t}: got {got}, protocol says {want}")
    piv = (g.groupby(["Source", "Target", "Seed"]).Skill.mean().reset_index()
             .groupby(["Source", "Target"]).Skill.mean().unstack())
    for t, want in EXPECTED_DIAG.items():
        try:
            got = float(piv.loc[t, t])
        except Exception:
            fail.append(f"in-climate {t}: missing"); continue
        if got < 0:
            fail.append(f"in-climate {t} is negative ({got:+.3f}) — lag structure broken")
        elif abs(got - want) > GATE_TOL:
            fail.append(f"in-climate {t}: got {got:+.3f}, Phase 13 has {want:+.3f}")
    return fail


def main():
    t0 = time.time()
    print("=" * 70)
    print("CONTROL F v3 — does the gap survive a physically general feature?")
    print("=" * 70, flush=True)

    data = {tag: load(tag, fname) for tag, fname in FILES}

    rows, sitecount = [], {}
    for featkey, cc, label in CONDITIONS:
        print(f"\n{'='*70}\nCONDITION: {label}"
              f"{'   [complete-case rows]' if cc else ''}\n{'='*70}", flush=True)
        rng = np.random.default_rng(RNG)
        tr, te = {}, {}
        for tag in CLIM:
            tr[tag], te[tag] = assemble(data[tag], featkey, cc, rng)

        ref = {}
        for tag in CLIM:
            t = te[tag]
            ref[tag] = rmse_by_site(t["y"], t["naive"], t["cap"], t["site"])
            sitecount[(label, tag)] = len(ref[tag])
            for s, r in ref[tag].items():
                rows.append(dict(Features=label, Source="-", Target=tag,
                                 Model="Persistence_naive", Seed=0, Site_ID=s,
                                 RMSE_kW=r, Skill=0.0))
        print("  scored sites: " + ", ".join(
            f"{t} {sitecount[(label,t)]}" for t in CLIM), flush=True)

        for src in CLIM:
            if tr[src] is None:
                continue
            Xtr, ytr = tr[src]
            for seed in SEEDS:
                r0 = np.random.default_rng(seed)
                idx = np.arange(len(ytr))
                if idx.size > MAX_TRAIN:
                    idx = r0.choice(idx, MAX_TRAIN, replace=False)
                m = HistGradientBoostingRegressor(random_state=seed, **GBM)
                m.fit(Xtr[idx], ytr[idx])
                for tgt in CLIM:
                    t = te[tgt]
                    yh = m.predict(t["X"])
                    for s, r in rmse_by_site(t["y"], yh, t["cap"], t["site"]).items():
                        b = ref[tgt].get(s)
                        rows.append(dict(Features=label, Source=src, Target=tgt,
                                         Model="GBM", Seed=seed, Site_ID=s,
                                         RMSE_kW=r, Skill=(1 - r/b) if b else np.nan))
                print(f"  {src:<7} -> all  seed {seed:<4} [{time.time()-t0:6.0f}s]", flush=True)

    res = pd.DataFrame(rows)
    out_csv = os.path.join(HERE, "phase19_feature_control_results.csv")
    res.to_csv(out_csv, index=False)
    print(f"\nwrote {out_csv}")

    fail = gate(res)
    if fail:
        print("\n" + "!" * 70)
        print("GATE FAILED — `common` does not reproduce Phase 13. No verdict.")
        for f in fail:
            print("  - " + f)
        print("!" * 70)
        sys.exit(2)
    print("\nGATE PASSED — `common` reproduces Phase 13 within tolerance.")

    g = res[res.Model == "GBM"]
    L = ["CONTROL F — feature-set control", "=" * 70,
         "Archives: DKASC, HKUST, PVDAQ (Ausgrid publishes no weather).",
         "Conditions 2 and 3 use identical complete-case rows and differ by one",
         "column, so no NaN reaches the model and missing-value handling cannot",
         "explain any difference between them. Irradiance enters at the target",
         "timestamp, the Phase 11 convention.", ""]
    for _, _, label in CONDITIONS:
        a, b, gp = pooled(g, label)
        L.append(f"{label:<15} same-climate {a:+.3f}   transferred {b:+.3f}   gap {gp:.3f}")
    L.append("")
    L.append("scored sites per condition:")
    for _, _, label in CONDITIONS:
        L.append(f"  {label:<15} " + ", ".join(
            f"{t} {sitecount.get((label,t),0)}" for t in CLIM))
    L.append("")

    _, _, g_cc = pooled(g, "common_cc")
    _, _, g_irr = pooled(g, "common+irr_cc")
    if g_cc <= 0:
        L.append("ABORT: the complete-case common-feature gap is not positive.")
        L.append("There is no gap on this subset to test, and no verdict follows.")
    else:
        L.append(f"Complete-case comparison: gap {g_cc:.3f} -> {g_irr:.3f}")
        L.append("")
        if g_irr > 0.5 * g_cc:
            L.append("VERDICT: the gap survives a physically general feature.")
            L.append("Feature impoverishment is EXCLUDED as the explanation.")
            if g_irr > g_cc:
                L.append("Note: irradiance WIDENS the gap. The learned power-from-")
                L.append("irradiance mapping is array-specific and does not transfer.")
        else:
            L.append("VERDICT: the gap more than halves once irradiance is available.")
            L.append("Feature impoverishment is NOT excluded. The paper's central")
            L.append("claim must be restated to reflect this.")

    L.append("")
    L.append("-- transfer matrices, skill vs naive persistence --")
    for _, _, label in CONDITIONS:
        d = g[g.Features == label]
        piv = (d.groupby(["Source", "Target", "Seed"]).Skill.mean().reset_index()
                 .groupby(["Source", "Target"]).Skill.mean().unstack())
        L.append(f"\n{label}:")
        L.append(piv.round(3).to_string())
    L.append("")
    L.append(f"rows written: {len(res):,}   elapsed: {time.time()-t0:.0f}s")

    txt = "\n".join(L)
    with open(os.path.join(HERE, "phase19_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print("\n" + txt)


if __name__ == "__main__":
    main()
