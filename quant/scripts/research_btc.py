"""Reference research run: rule ensemble and walk-forward ML on BTC, vs buy-and-hold.

Run with:  QT_DATA_DIR=./data .venv/bin/python scripts/research_btc.py
"""
import warnings; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np

from qt.data import Catalog
from qt.bars import klines_to_bars
from qt import features as F, alphas as A
from qt.labels import LabelSpec
from qt.models import ModelSpec
from qt.backtest import BacktestConfig, buy_and_hold, compare, rule_backtest
from qt.backtest.walkforward import WalkForwardSpec, walk_forward
from qt.validation import deflated_sharpe_ratio, bootstrap_returns

cat = Catalog()
k = cat.read_indexed("klines_1h", "binance", "BTCUSDT")
bars = klines_to_bars(k)
bars.index = pd.to_datetime(bars["ts"], unit="ms", utc=True); bars.index.name = "dt"
fm = F.build_features(bars, symbol="BTCUSDT")
bt_bars = bars.loc[fm.X.index]
print(f"bars={bars.shape}  features={fm.X.shape}  {bars.index.min()} -> {bars.index.max()}")

# --- 1. rule ensemble -------------------------------------------------------
sig = A.compute_all(bars, fm.X, warn_missing=False)
fwd = np.log(bars["close"]).diff(24).shift(-24).reindex(fm.X.index)
combined, _ = A.combine(sig, fwd, A.EnsembleSpec(method="ic_weighted", window=720, shrinkage=0.5))
ens = rule_backtest(bt_bars, combined, symbol="BTCUSDT")

# --- 2. walk-forward ML -----------------------------------------------------
wf = walk_forward(
    bt_bars, fm.X,
    label_spec=LabelSpec(horizon_bars=24, pt_sl=(2.0, 1.0)),
    model_spec=ModelSpec(kind="lgbm", calibrate=False),
    wf_spec=WalkForwardSpec(train_bars=8760, test_bars=2160, embargo_bars=48),
    backtest_config=BacktestConfig(),
    symbol="BTCUSDT",
)
print("\nwalk-forward windows:")
print(wf.windows.to_string())

bench = buy_and_hold(bt_bars)
tbl = compare({"rule_ensemble": ens, "walkforward_ml": wf.backtest, "buy_hold": bench}).T
rows = ["cagr","annual_vol","sharpe","sortino","calmar","max_drawdown","turnover_annual",
        "cost_share_of_gross","n_trades","avg_slippage_bps","total_return"]
print("\n" + tbl.loc[[r for r in rows if r in tbl.index]].to_string())

# --- 3. is any of this distinguishable from luck? ---------------------------
for name, res in (("rule_ensemble", ens), ("walkforward_ml", wf.backtest)):
    dsr = deflated_sharpe_ratio(res.returns, n_trials=20, sr_variance=0.25)
    print(f"\n{name}: sharpe={dsr['sharpe']:.2f}  benchmark(luck)={dsr['benchmark_sharpe']:.2f}  "
          f"DSR={dsr['deflated_sharpe']:.3f}  -> {dsr['verdict']}")
    bs = bootstrap_returns(res.returns, n_samples=300, block_size=24)
    if not bs.sharpe.empty:
        print("  bootstrap sharpe  5%/50%/95%: "
              f"{bs.sharpe.quantile(.05):.2f} / {bs.sharpe.quantile(.5):.2f} / {bs.sharpe.quantile(.95):.2f}")
        print("  bootstrap max DD  5%/50%/95%: "
              f"{bs.max_drawdown.quantile(.05):.1%} / {bs.max_drawdown.quantile(.5):.1%} / {bs.max_drawdown.quantile(.95):.1%}")
