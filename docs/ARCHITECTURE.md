# Architecture Documentation: S&P 500 Top N Strategy Engine

This document outlines the software architecture, quantitative mathematical mechanics, and data structures of the S&P 500 Top N Strategy backtesting engine and reporting suite.

---

## 1. System Overview & Component Hierarchy

The system is decoupled into seven distinct layers, strictly adhering to single-responsibility principles and zero external dependencies (Python 3 standard library only):

```mermaid
graph TD
    CLI[run_backtest.py<br>CLI Entrypoint] --> SIM[PortfolioSimulator<br>engine/backtest.py]
    
    SIM --> DL[DataLoader<br>engine/data_loader.py]
    SIM --> SEL[BaseSelector<br>engine/selector.py]
    SIM --> TAX[FIFOTaxLotManager<br>engine/tax_lots.py]
    SIM --> MOD[Domain Models<br>engine/models.py]
    
    DL --> DATA[(JSON Datasets<br>data/)]
    
    SIM --> MET[Metrics Engine<br>engine/metrics.py]
    SIM --> EXP[Report Exporters<br>engine/exporters.py]
    
    EXP --> CSV[CSV Reports<br>outputs/]
    EXP --> GAS[Google Apps Script<br>scripts/google_apps_script.js]
```

### Layer Responsibilities

| Layer / File | Responsibility |
| :--- | :--- |
| [`engine/models.py`](../engine/models.py) | Pure immutable/mutable typed dataclasses (`ConstituentSnapshot`, `HoldingTarget`, `TaxLot`, `TradeOrder`, `AnnualLedgerEntry`, `StrategyResult`). |
| [`engine/data_loader.py`](../engine/data_loader.py) | Loads point-in-time constituent snapshots, split-adjusted close prices (1994–2024), and official `^GSPC` benchmark levels from JSON data stores. |
| [`engine/tax_lots.py`](../engine/tax_lots.py) | Maintains FIFO tax-lot queues per ticker, executes partial lot depletion, accumulates realized gains, and nets gains against prior loss carryforwards. |
| [`engine/selector.py`](../engine/selector.py) | Ranks constituents and calculates target weights normalized to 100% ($w_i = W_i / \sum W_j$). Supports market cap and 1-year trailing momentum rules. |
| [`engine/backtest.py`](../engine/backtest.py) | Two-phase rebalance simulation engine enforcing cash neutrality, self-financing, and zero margin debt ($cash \ge 0.0$). |
| [`engine/metrics.py`](../engine/metrics.py) | Pure mathematical calculation of CAGR, Cumulative Return, Max Drawdown, Turnover, Tax Drag, Alpha, and terminal liquidation metrics. |
| [`engine/exporters.py`](../engine/exporters.py) | Formats CSV audit files and generates standalone Google Apps Script for interactive Google Sheets dashboards. |

---

## 2. Two-Phase Rebalancing Mechanics & Tax Settlement

A naive rebalancing algorithm suffers from circular dependency when capital gains taxes are involved:
1. Selling overweight stocks creates capital gains taxes.
2. The tax liability reduces net investable equity.
3. Lower net equity changes the dollar targets for all positions, altering required sell amounts.

To resolve this circularity while guaranteeing **strict self-financing without unmodeled margin leverage ($cash \ge 0.0$)**, the engine executes a deterministic two-phase rebalancing cycle:

```mermaid
sequenceDiagram
    autonumber
    participant Sim as PortfolioSimulator
    participant Sel as BaseSelector
    participant Tax as FIFOTaxLotManager

    Note over Sim: Year-End Valuation (t+1)
    Sim->>Sim: Price held shares: V_pre = sum(S_held * P_curr)
    Sim->>Sel: select(universe, n) -> Target Weights w_i
    
    Note over Sim: Phase 1: Provisional Trims & Exits
    Sim->>Sim: Compute provisional target shares: S_prov = (V_pre * w_i) / P_curr
    Sim->>Tax: Liquidate 100% of dropped constituents
    Sim->>Tax: Trim overweight stocks where S_held > S_prov
    Tax-->>Sim: Realized gains & sell proceeds -> cash balance
    
    Note over Sim: Phase 2: Tax Settlement & Convergence
    Sim->>Tax: settle_annual_taxes(tax_rate, t+1) -> (TaxPaid, LossCF)
    Sim->>Sim: Pay taxes from cash: cash = cash - TaxPaid, V_net = V_pre - TaxPaid
    
    alt Overweight Excess Exists (TaxPaid > 0)
        Sim->>Tax: Secondary trim: S_excess = (TaxPaid * w_i) / P_curr
        Tax-->>Sim: Additional proceeds -> cash balance
    end
    
    Note over Sim: Net Capital Reinvestment
    Sim->>Sim: Final Target Shares: S_final = (V_net * w_i) / P_curr
    Sim->>Sim: Clamp buys to available cash: cost = min(cost, max(0.0, cash))
    Sim->>Tax: add_lot(ticker, shares_bought, P_curr, t+1)
    Sim->>Sim: Cash dust snapped to 0.0 (tolerance 1e-5)
```

### Mathematical Proof of Self-Financing & Exact Target Weights
Let $V_{\text{pre}} = \sum_i S_i P_i$ be pre-tax portfolio equity.  
Let $T$ be the tax liability determined by sales.  
The net investable equity is $V_{\text{net}} = V_{\text{pre}} - T$.

1. Overweight holdings were provisionally trimmed to $V_{\text{pre}} w_i$.  
2. Their final target is $V_{\text{net}} w_i = (V_{\text{pre}} - T) w_i = V_{\text{pre}} w_i - T w_i$.  
3. Trimming the excess shares releases proceeds equal to:
   $$\sum_{i \in \text{Overweight}} T w_i = T \sum_{i \in \text{Overweight}} w_i$$
4. Adding these proceeds to remaining cash $(\text{GrossProceeds} - T)$ provides the exact cash needed to purchase all underweight holdings up to $V_{\text{net}} w_j$:
   $$\text{Cash Available} = \sum_{j \in \text{Underweight}} (V_{\text{net}} w_j - V_{\text{held}, j})$$
5. As a result, every position exactly achieves target weight $w_k$, portfolio value equals $V_{\text{net}}$, and residual cash is precisely $0.0$.

---

## 3. FIFO Tax-Lot Accounting Model

Each asset purchase creates an immutable `TaxLot(lot_id, ticker, shares, purchase_price, purchase_year)`.

When shares are sold:
1. **FIFO Depletion**: The earliest purchase lots are depleted first.
2. **Partial Lot Splits**: If a sale depletes a fraction of a lot, the sold fraction is logged with realized capital gain $(P_{\text{sell}} - P_{\text{buy}}) \times \text{shares}$, while remaining shares stay in the lot with unchanged purchase price and year.
3. **Loss Carryforward Netting**:
   $$NetTaxableGain_{t+1} = RealizedGain_{t+1} - LossCarryforward_{t}$$
   - If $NetTaxableGain_{t+1} > 0$: $TaxPaid = NetTaxableGain_{t+1} \times \tau$, $LossCarryforward_{t+1} = 0$.
   - If $NetTaxableGain_{t+1} \le 0$: $TaxPaid = 0$, $LossCarryforward_{t+1} = |NetTaxableGain_{t+1}|$.
4. **Terminal Liquidation**:
   Embedded unrealized gain is computed across all remaining lots:
   $$UnrealizedGain = \sum_{\text{lots}} (P_{\text{terminal}} - P_{\text{buy}}) \times \text{shares}$$
   Terminal tax nets against any accumulated loss carryforward:
   $$TerminalTax = \max(0.0, UnrealizedGain - LossCarryforward) \times \tau$$
   $$PostLiquidationWealth = PreLiquidationWealth - TerminalTax$$

---

## 4. Pluggable Factor Selection

New quantitative selection models extend [`BaseSelector`](../engine/selector.py):

```python
from engine.selector import BaseSelector
from engine.models import ConstituentSnapshot, HoldingTarget
from typing import Sequence, List, Optional

class CustomQualitySelector(BaseSelector):
    def select(
        self, universe: Sequence[ConstituentSnapshot], n: Optional[int] = None
    ) -> List[HoldingTarget]:
        eff_n = self.n if n is None else n
        # Filter and rank universe
        ranked = sorted(universe, key=lambda c: c.market_cap_weight, reverse=True)[:eff_n]
        # Normalize weights
        weights = self._compute_weights(ranked, self.weight_by)
        return [HoldingTarget(ticker=c.ticker, target_weight=w) for c, w in zip(ranked, weights)]
```

---

## 5. Google Sheets Dynamic Integration Architecture

The generated [`scripts/google_apps_script.js`](../scripts/google_apps_script.js) utilizes a multi-tier data pipeline:

1. **Pre-Computed Scenario Matrix**: Simulations for standard tax brackets ($0.0\%, 15.0\%, 20.0\%, 30.0\%, 37.0\%$) across all horizons and $N \in \{3, 5, 10\}$ are pre-computed in Python and embedded into a hidden `Scenario Data` sheet.
2. **Interactive Dropdown Trigger**: Cell `B2` on `Executive Summary` features a dropdown with data validation.
3. **Dynamic Formula Linking**: Summary cards and comparison tables query the scenario matrix via dynamic lookup formulas:
   ```excel
   =VLOOKUP($A10 & "_" & $B10 & "_" & TEXT($B$2, "0.0%"), 'Scenario Data'!$A$2:$R$100, COLUMN(), FALSE)
   ```
   This provides instantaneous updates upon dropdown selection without lag or formula errors.
4. **On-Demand Custom Recalculation**: A custom Google Apps Script function `RECALCULATE_STRATEGY(customRate)` is included for non-standard tax rates (e.g. $24.5\%$).
