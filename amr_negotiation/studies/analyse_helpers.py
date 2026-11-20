"""Statistics helpers shared by analyse.py and analyse_r2.py."""
import math

import pandas as pd


def ci(x):
    x = pd.Series(x).dropna()
    if len(x) < 2: return float('nan')
    return 1.96 * x.std(ddof=1) / math.sqrt(len(x))
def fmt(m, c, d=1): return f"{m:.{d}f} ± {c:.{d}f}" if not (isinstance(c, float) and math.isnan(c)) else f"{m:.{d}f}"
def wilson(k, n):
    if n == 0: return (float('nan'),) * 2
    z = 1.96; p = k / n; den = 1 + z * z / n; c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)
def rate(s):
    k, n = int(s.sum()), len(s); lo, hi = wilson(k, n); return f"{100*k/n:.1f}% [{100*lo:.0f}–{100*hi:.0f}]"
def keycols(df):
    base = {'study','label','seed','success','deadlock','collision','makespan','total_delay','max_delay','wdelay','jain','reverse_dist','yielder','n_yielders','refuge','rule','msgs','msgs_dropped','time_to_decide','agreement','n_yields','min_clearance','wall_hits','n_decisions','pred_yielder_delay','pred_proceeder_delay'}
    return [c for c in df.columns if c not in base and not c.startswith(('delay_', 'reverse_', 'bid_'))]
def paired(df, ref='oracle', metric='total_delay'):
    k = keycols(df) + ['seed']
    o = df[df.label == ref][k + [metric, 'yielder']].rename(columns={metric: 'ref', 'yielder': 'ref_yielder'})
    m = df.merge(o, on=k, how='left'); m['regret'] = m[metric] - m['ref']; return m
