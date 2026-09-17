# Changelog

All notable changes to CrossClimatePV are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A version bump means the evaluation protocol changed. Results produced under
different major versions are not comparable, and the leaderboard records the
protocol version alongside every entry.

## [1.0.0] — 2026-08-13

First public release. This is the version the paper reports.

### Added

- Harmonization pipeline for four public archives (DKASC, HKUST, Ausgrid,
  PVDAQ) into one schema — 23,312,924 rows, 369 selected sites, 345 scored,
  five Köppen classes (BWh, Cwa, Cfa, BSk, Dfb).
- Frozen evaluation protocol: chronological 70/15/15 split with no shuffling,
  per-site capacity normalization at the 99.5th percentile of positive output,
  a five-feature common set (normalized power plus four cyclical time
  features), and rare-event labels from a clipping proxy and a
  cloud-transient proxy.
- Five baselines under matched budgets — naive persistence, MLP, LSTM,
  Transformer and gradient boosting. 100,000 training windows, three seeds
  (42, 7, 123), identical per-site test rows.
- Cross-climate transfer matrix, four sources by four targets.
- Leave-one-climate-out evaluation.
- Horizon sweep at 15, 30, 60 and 180 minutes.
- Rare-event threshold sensitivity across 405 settings per dataset.
- Weather ablation, common features against common plus weather.
- Five confound controls isolating sampling interval, site count, baseline
  strength, site novelty and installation class.
- Statistical testing — Wilcoxon signed-rank paired on site, Holm–Bonferroni
  correction, matched-pairs rank-biserial effect size.
- `protocol/` — split definitions, capacity constants and rare-event label
  counts, so the evaluation reproduces without redistributing source data.
- `results/` — per-site results for every model, seed and experiment.
- `leaderboard.md` and submission instructions.

### Known limitations

- Climate cannot be fully separated from data provenance. Four controls
  exclude alternative explanations and one quantifies installation class at
  roughly a quarter of the gap; the remainder is the joint contribution of
  climate zone and provenance. Separating them needs one installation class
  and one instrumentation standard deployed across multiple Köppen zones,
  which no public PV dataset currently provides.
- PVDAQ uses a per-site chronological split rather than a global one, because
  its systems were commissioned across 2007–2023. Its internal comparisons are
  consistent; its test window is not calendar-aligned across systems.
- DKASC contributes a single site, so it carries no paired significance test.
- Weather is excluded from the common feature set by design, since
  cross-climate transfer is not computable without a shared input width. The
  cost of that choice is measured in the weather ablation rather than assumed.

[1.0.0]: https://github.com/shahoismael/crossclimatepv/releases/tag/v1.0.0

## [1.1.0] - 2026-09-10

### Added
- Control F (`evaluation/phase19_feature_control.py`): feature-set control. Adding
  irradiance on identical complete-case rows widens the cross-climate gap from
  0.105 to 0.355 rather than closing it, excluding feature impoverishment as the
  explanation. Results in `results/phase19_feature_control_results.csv`.
- `results/phase6_transfer_matrix_results.csv` (untuned run behind Appendix Table A.1).

### Changed
- Project renamed SolarBench -> CrossClimatePV. The name SolarBench was taken by
  arXiv:2609.06187 (Nie et al., 2026), an unrelated image-based nowcasting benchmark.
- `solarbench_config.m` -> `crossclimatepv_config.m`; `SOLARBENCH_DATA` still honoured
  as a legacy environment variable.
- README: training budgets corrected (MLP uses 150,000 rows, not 100,000 windows);
  pooled shortest-horizon skill corrected to +0.054.
