import unittest
from engine.models import (
    ConstituentSnapshot,
    HoldingTarget,
    TaxLot,
    TradeOrder,
    AnnualLedgerEntry,
    StrategyResult,
)


class TestModels(unittest.TestCase):
    def test_holding_target(self):
        target = HoldingTarget(
            ticker="AAPL",
            target_weight=0.5,
            target_dollar=5000.0,
            target_shares=25.0,
        )
        self.assertEqual(target.ticker, "AAPL")
        self.assertEqual(target.target_weight, 0.5)
        self.assertEqual(target.target_dollar, 5000.0)
        self.assertEqual(target.target_shares, 25.0)

    def test_tax_lot(self):
        lot = TaxLot(
            lot_id="lot_1",
            ticker="MSFT",
            shares=10.0,
            purchase_price=100.0,
            purchase_year=2020,
        )
        self.assertEqual(lot.lot_id, "lot_1")
        self.assertEqual(lot.ticker, "MSFT")
        self.assertEqual(lot.shares, 10.0)
        self.assertEqual(lot.purchase_price, 100.0)
        self.assertEqual(lot.purchase_year, 2020)
        self.assertEqual(lot.cost_basis(), 1000.0)

    def test_tax_lot_partial_or_zero_shares(self):
        zero_lot = TaxLot(
            lot_id="lot_zero",
            ticker="MSFT",
            shares=0.0,
            purchase_price=150.0,
            purchase_year=2021,
        )
        self.assertEqual(zero_lot.cost_basis(), 0.0)

        fractional_lot = TaxLot(
            lot_id="lot_frac",
            ticker="GOOGL",
            shares=2.5,
            purchase_price=120.0,
            purchase_year=2022,
        )
        self.assertAlmostEqual(fractional_lot.cost_basis(), 300.0)

    def test_constituent_snapshot(self):
        snapshot = ConstituentSnapshot(
            ticker="NVDA",
            name="NVIDIA Corp",
            market_cap_weight=0.065,
            trailing_1y_return=2.38,
            year=2024,
        )
        self.assertEqual(snapshot.ticker, "NVDA")
        self.assertEqual(snapshot.name, "NVIDIA Corp")
        self.assertEqual(snapshot.market_cap_weight, 0.065)
        self.assertEqual(snapshot.trailing_1y_return, 2.38)
        self.assertEqual(snapshot.year, 2024)

    def test_trade_order(self):
        order_default = TradeOrder(
            ticker="AAPL",
            action="BUY",
            shares=10.0,
            price=150.0,
            year=2021,
        )
        self.assertEqual(order_default.ticker, "AAPL")
        self.assertEqual(order_default.action, "BUY")
        self.assertEqual(order_default.shares, 10.0)
        self.assertEqual(order_default.price, 150.0)
        self.assertEqual(order_default.year, 2021)
        self.assertEqual(order_default.realized_gain, 0.0)

        order_sell = TradeOrder(
            ticker="AAPL",
            action="SELL",
            shares=5.0,
            price=180.0,
            year=2022,
            realized_gain=150.0,
        )
        self.assertEqual(order_sell.realized_gain, 150.0)

    def test_annual_ledger_entry(self):
        entry = AnnualLedgerEntry(
            year=2020,
            start_value=100000.0,
            gross_return=0.15,
            ending_value_pretax=115000.0,
            realized_capital_gain=5000.0,
            net_taxable_gain=5000.0,
            tax_paid=1500.0,
            loss_carryforward=0.0,
            ending_value_aftertax=113500.0,
            spx_return=0.184,
            turnover=0.25,
            holdings={"AAPL": 50.0, "MSFT": 40.0},
        )
        self.assertEqual(entry.year, 2020)
        self.assertEqual(entry.start_value, 100000.0)
        self.assertEqual(entry.gross_return, 0.15)
        self.assertEqual(entry.ending_value_pretax, 115000.0)
        self.assertEqual(entry.realized_capital_gain, 5000.0)
        self.assertEqual(entry.net_taxable_gain, 5000.0)
        self.assertEqual(entry.tax_paid, 1500.0)
        self.assertEqual(entry.loss_carryforward, 0.0)
        self.assertEqual(entry.ending_value_aftertax, 113500.0)
        self.assertEqual(entry.spx_return, 0.184)
        self.assertEqual(entry.turnover, 0.25)
        self.assertEqual(entry.holdings, {"AAPL": 50.0, "MSFT": 40.0})

    def test_strategy_result(self):
        result = StrategyResult(
            strategy_name="Top_5_MarketCap",
            n=5,
            start_year=2014,
            end_year=2024,
            is_after_tax=True,
            tax_rate=0.30,
            initial_capital=100000.0,
            final_equity=350000.0,
            cagr=0.133,
            cumulative_return=2.50,
            max_drawdown=-0.22,
            total_taxes_paid=45000.0,
            pre_liquidation_wealth=350000.0,
            post_liquidation_wealth=310000.0,
            post_liquidation_cagr=0.120,
            annual_history=[],
        )
        self.assertEqual(result.strategy_name, "Top_5_MarketCap")
        self.assertEqual(result.n, 5)
        self.assertEqual(result.start_year, 2014)
        self.assertEqual(result.end_year, 2024)
        self.assertTrue(result.is_after_tax)
        self.assertEqual(result.tax_rate, 0.30)
        self.assertEqual(result.initial_capital, 100000.0)
        self.assertEqual(result.final_equity, 350000.0)
        self.assertEqual(result.cagr, 0.133)
        self.assertEqual(result.cumulative_return, 2.50)
        self.assertEqual(result.max_drawdown, -0.22)
        self.assertEqual(result.total_taxes_paid, 45000.0)
        self.assertEqual(result.pre_liquidation_wealth, 350000.0)
        self.assertEqual(result.post_liquidation_wealth, 310000.0)
        self.assertEqual(result.post_liquidation_cagr, 0.120)
        self.assertEqual(result.annual_history, [])


if __name__ == "__main__":
    unittest.main()
