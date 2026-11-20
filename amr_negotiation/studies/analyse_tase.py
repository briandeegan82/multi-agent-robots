"""T-ASE statistics (revision WP2): bootstrap and paired CIs, parity tests, Holm correction, failure imputation.

    python studies/analyse_tase.py [RESULTS_RAW_DIR] [REPORT_DIR]   # -> report/tase_stats.md, report/tase_numbers.csv

Conventions
- Excess delay Δπ is computed per draw (grid cell × seed) against the best forced yielder on the same draw
  (`oracle`, or `oracle_w` for urgency-weighted delay).
- Primary metric: failed episodes are charged n_robots × t_max (180 s each), so deadlocks count against a policy.
  Secondary: success-only means (the convention of analyse.py).
- CIs: 95% percentile bootstrap (2,000 resamples) that resamples seeds within each grid cell (stratified), and the
  normal-approximation CI over all draws (pooled), shown side by side.
- Parity: two one-sided tests (TOST) against ±0.5 s on the paired per-draw differences; "equivalent" if both
  one-sided p < 0.05, otherwise "inconclusive" unless the paired difference is significant.
- Holm–Bonferroni over the family of paired comparisons that back Table VII.
- Rates: Wilson 95% intervals, and the exact Clopper–Pearson upper bound for zero counts.
- S7: `rules_proximity` and `oracle` do not depend on σ, so their rows are deduplicated before counting N.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results_raw'
REP = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / 'report'
T_MAX, NB, EQ = 180.0, 2000, 0.5
RNG = np.random.default_rng(0)
OUTCOME = {'study', 'label', 'seed', 'success', 'deadlock', 'collision', 'makespan', 'total_delay', 'max_delay',
           'wdelay', 'jain', 'reverse_dist', 'yielder', 'n_yielders', 'refuge', 'rule', 'msgs', 'msgs_dropped',
           'time_to_decide', 'agreement', 'n_yields', 'min_clearance', 'wall_hits', 'n_decisions',
           'pred_yielder_delay', 'pred_proceeder_delay'}
NUMBERS = []


def grid_cols(df):
    return [c for c in df.columns if c not in OUTCOME and not c.startswith(('delay_', 'reverse_', 'bid_'))]


def load(name):
    df = pd.read_csv(RAW / f'{name}.csv.gz')
    for c in ('success', 'deadlock', 'collision'):
        df[c] = df[c].astype(bool)
    return df


def per_draw(df, metric, ref, impute=True, cells=None):
    """Wide table: one row per draw, one column per label, values = metric (failures imputed or NaN)."""
    cells = cells or [c for c in grid_cols(df) if c not in ('agents.1.start_delay',)]
    n_rob = sum(c.startswith('delay_') for c in df.columns)
    v = df[metric].where(df.success, n_rob * T_MAX if impute else np.nan)
    w = df.assign(v=v).pivot_table(index=cells + ['seed'], columns='label', values='v', aggfunc='first')
    return w.sub(w[ref], axis=0).drop(columns=[ref]), cells


def boot_mean(x, strata):
    """Stratified percentile bootstrap of the mean of x (resample within each stratum)."""
    x = np.asarray(x, float); ok = ~np.isnan(x); x, strata = x[ok], np.asarray(strata)[ok]
    if len(x) < 2:
        return float('nan'), float('nan')
    groups = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    means = np.empty(NB)
    for b in range(NB):
        idx = np.concatenate([g[RNG.integers(0, len(g), len(g))] for g in groups])
        means[b] = x[idx].mean()
    return tuple(np.percentile(means, [2.5, 97.5]))


def summ(x, strata):
    x = pd.Series(np.asarray(x, float)).dropna()
    m = x.mean(); h = 1.96 * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float('nan')
    lo, hi = boot_mean(x.values, np.asarray(strata)[x.index] if len(x) else [])
    return m, h, lo, hi, len(x)


def tost(d):
    d = pd.Series(d).dropna()
    if len(d) < 2 or d.std(ddof=1) == 0:
        return (0.0 if abs(d.mean()) < EQ else 1.0), float('nan')
    se = d.std(ddof=1) / math.sqrt(len(d)); df_ = len(d) - 1
    p_lo = 1 - stats.t.cdf((d.mean() + EQ) / se, df_); p_hi = stats.t.cdf((d.mean() - EQ) / se, df_)
    return max(p_lo, p_hi), stats.ttest_1samp(d, 0).pvalue


def wilson(k, n):
    z = 1.96; p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def cp_upper(n):
    return 1 - 0.025 ** (1 / n)  # exact one-sided 97.5% Clopper–Pearson bound for 0/n


def rec(key, value, source, method):
    NUMBERS.append({'key': key, 'value': value, 'source': source, 'method': method})


def excess_table(md, name, metric, ref, labels, title):
    df = load(name)
    md.append(f'\n## {title}\n')
    md.append('| policy | N | Δπ imputed, mean | pooled ±CI | stratified bootstrap 95% CI | Δπ success-only | success [Wilson 95%] |')
    md.append('|---|---|---|---|---|---|---|')
    w_imp, cells = per_draw(df, metric, ref, True)
    w_ok, _ = per_draw(df, metric, ref, False)
    strata = w_imp.reset_index()[cells].astype(str).agg('|'.join, axis=1).values
    for lab in labels:
        if lab not in w_imp:
            continue
        m, h, lo, hi, n = summ(w_imp[lab].values, strata)
        mo, ho, *_ = summ(w_ok[lab].values, strata)
        g = df[df.label == lab]; k = int(g.success.sum()); wl, wh = wilson(k, len(g))
        md.append(f'| `{lab}` | {n} | {m:.2f} | ±{h:.2f} | [{lo:.2f}, {hi:.2f}] | {mo:.2f} ± {ho:.2f} | '
                  f'{100 * k / len(g):.1f}% [{100 * wl:.1f}, {100 * wh:.1f}] |')
        rec(f'{name}.{lab}.excess_imputed', round(m, 2), f'results_raw/{name}.csv.gz', f'{metric} - {ref}, failures={T_MAX:.0f}s/robot')
        rec(f'{name}.{lab}.excess_success_only', round(mo, 2), f'results_raw/{name}.csv.gz', f'{metric} - {ref}, successes')
        rec(f'{name}.{lab}.success_rate', round(k / len(g), 4), f'results_raw/{name}.csv.gz', 'success / episodes')
    return df, w_imp, strata


def paired_rows(md, fam, name, w, strata, pairs):
    for a, b in pairs:
        if a not in w or b not in w:
            continue
        d = (w[a] - w[b]).values
        m, h, lo, hi, n = summ(d, strata)
        p_eq, p = tost(d)
        fam.append({'study': name, 'a': a, 'b': b, 'n': n, 'mean': m, 'lo': lo, 'hi': hi, 'p': p, 'p_tost': p_eq})


def main():
    md = ['# T-ASE statistics (WP2)', '', __doc__.split('Conventions', 1)[1].strip()]
    fam = []
    pols = ['reactive', 'fixed_priority', 'rules_default', 'rules_proximity', 'cost_bid']
    for name, metric, ref, title in [
            ('S1_baseline', 'total_delay', 'oracle', 'S1 single bay: excess delay vs best forced yielder [s]'),
            ('S2_asymmetry', 'wdelay', 'oracle_w', 'S2 heterogeneous robots: urgency-weighted excess delay [s]'),
            ('S4_two_bays', 'total_delay', 'oracle', 'S4 two bays: excess delay [s]')]:
        df, w, strata = excess_table(md, name, metric, ref, pols, title)
        paired_rows(md, fam, name, w, strata, [('rules_proximity', 'fixed_priority'), ('rules_proximity', 'cost_bid'),
                                                 ('rules_default', 'fixed_priority'), ('cost_bid', 'fixed_priority'),
                                                 ('reactive', 'fixed_priority')])
        if name == 'S1_baseline':
            r = df[df.label == 'reactive']; dl = int(r.deadlock.sum())
            md.append(f'\nReactive deadlocks: {dl}/{len(r)} ({100 * dl / len(r):.1f}%). Negotiating policies: '
                      f'0 failures; Clopper–Pearson 97.5% upper bound {100 * cp_upper(len(r)):.2f}% '
                      f'(Wilson {100 * wilson(0, len(r))[1]:.2f}%).')
            rec('S1.reactive.deadlock_rate', round(dl / len(r), 4), 'results_raw/S1_baseline.csv.gz', 'deadlock / episodes')
            ok = df[df.success]
            ratio = ok[ok.label == 'reactive'].total_delay.mean() / ok[ok.label == 'fixed_priority'].total_delay.mean()
            imp = df.total_delay.where(df.success, 2 * T_MAX)
            ratio_i = imp[df.label == 'reactive'].mean() / imp[df.label == 'fixed_priority'].mean()
            md.append(f'Reactive / fixed-priority mean total delay: {ratio:.2f}× (successes), {ratio_i:.2f}× '
                      f'(deadlocks charged 2 × {T_MAX:.0f} s; reactive mean {imp[df.label == "reactive"].mean():.1f} s).')
            rec('S1.reactive_over_fixed.delay_ratio_success', round(ratio, 2), 'results_raw/S1_baseline.csv.gz', 'mean ratio')
            rec('S1.reactive_over_fixed.delay_ratio_imputed', round(ratio_i, 2), 'results_raw/S1_baseline.csv.gz', 'mean ratio, deadlock=360 s')

    # S7 (deduplicated), paired cost_bid - rules_proximity per sigma
    s7 = load('S7_noisy_bids')
    indep = s7.label != 'cost_bid'
    dedup = pd.concat([s7[~indep], s7[indep & (s7.bid_sigma == 0.0)]])
    md.append(f'\n## S7 bid noise (single bay)\n\nRows: {len(s7)} stored, {len(dedup)} unique '
              f'(σ-independent `rules_proximity`/`oracle` rows deduplicated).\n')
    md.append('| σ | cost_bid Δπ | stratified 95% CI | cost_bid − rules_proximity (paired) | 95% CI | p | TOST ±0.5 s p |')
    md.append('|---|---|---|---|---|---|---|')
    base = s7[indep & (s7.bid_sigma == 0.0)]
    for sg, g in s7[~indep].groupby('bid_sigma'):
        sub = pd.concat([g, base])
        w, cells = per_draw(sub.drop(columns='bid_sigma'), 'total_delay', 'oracle', True, ['bays.0.x'])
        strata = w.reset_index()['bays.0.x'].astype(str).values
        m, h, lo, hi, n = summ(w['cost_bid'].values, strata)
        d = (w['cost_bid'] - w['rules_proximity']).values
        dm, dh, dlo, dhi, _ = summ(d, strata); p_eq, p = tost(d)
        md.append(f'| {sg} | {m:.2f} | [{lo:.2f}, {hi:.2f}] | {dm:+.2f} | [{dlo:+.2f}, {dhi:+.2f}] | {p:.3f} | {p_eq:.3f} |')
        fam.append({'study': f'S7 σ={sg}', 'a': 'cost_bid', 'b': 'rules_proximity', 'n': n, 'mean': dm, 'lo': dlo,
                    'hi': dhi, 'p': p, 'p_tost': p_eq})
        rec(f'S7.sigma{sg}.cost_bid.excess', round(m, 2), 'results_raw/S7_noisy_bids.csv.gz', 'total_delay - oracle')
        rec(f'S7.sigma{sg}.cost_minus_prox', round(dm, 2), 'results_raw/S7_noisy_bids.csv.gz', 'paired per draw')

    # Holm over the family
    f = pd.DataFrame(fam).sort_values('p').reset_index(drop=True)
    m_ = len(f); f['p_holm'] = np.minimum(1, np.maximum.accumulate((m_ - f.index) * f.p.fillna(1)))
    f['verdict'] = np.select([f.p_holm < 0.05, f.p_tost < 0.05], ['different', 'equivalent (±0.5 s)'], 'inconclusive')
    md.append(f'\n## Paired comparisons behind Table VII (Holm over {m_} tests)\n')
    md.append('| study | A − B | N | mean | stratified 95% CI | p | Holm p | TOST p | verdict |')
    md.append('|---|---|---|---|---|---|---|---|---|')
    for r in f.sort_values(['study', 'a', 'b']).itertuples():
        md.append(f'| {r.study} | `{r.a}` − `{r.b}` | {r.n} | {r.mean:+.2f} | [{r.lo:+.2f}, {r.hi:+.2f}] | '
                  f'{r.p:.3g} | {r.p_holm:.3g} | {r.p_tost:.3g} | {r.verdict} |')
        rec(f'{r.study}.{r.a}-{r.b}', round(r.mean, 2), 'tase_stats.md', f'paired, Holm p={r.p_holm:.3g}, {r.verdict}')

    # episode counts
    files = sorted(RAW.glob('*.csv.gz'))
    counts = {p.name: len(pd.read_csv(p, usecols=[0])) for p in files}
    md.append('\n## Episode counts\n\n| file | rows |\n|---|---|')
    md += [f'| `{k}` | {v} |' for k, v in counts.items()]
    md.append(f'| **total** | {sum(counts.values())} |')
    rec('episodes.total_rows', sum(counts.values()), 'results_raw/*.csv.gz', 'sum of rows')
    commit = (RAW / 'COMMIT').read_text().strip() if (RAW / 'COMMIT').exists() else 'unknown'
    md.insert(1, f'\nData: `results_raw/` produced at commit `{commit}`.\n')
    REP.mkdir(exist_ok=True)
    (REP / 'tase_stats.md').write_text('\n'.join(md) + '\n')
    pd.DataFrame(NUMBERS).to_csv(REP / 'tase_numbers.csv', index=False)
    print('\n'.join(md))


if __name__ == '__main__':
    main()
