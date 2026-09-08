"""Unit tests for FIFOTaxLotManager and capital loss carryforward handling."""

import unittest
from engine.tax_lots import FIFOTaxLotManager
from engine.models import TaxLot


class TestFIFOTaxLotManager(unittest.TestCase):
    """Test suite for FIFO tax-lot tracking, sale depletion, and tax settlement."""

    def setUp(self):
        self.manager = FIFOTaxLotManager()

    def test_single_lot_addition_and_full_sale(self):
        """1. Single lot addition and full sale (exact gain calculation)."""
        lot = self.manager.add_lot(ticker="AAPL", shares=10.0, price=100.0, year=2020)
        self.assertIsInstance(lot, TaxLot)
        self.assertEqual(lot.ticker, "AAPL")
        self.assertAlmostEqual(lot.shares, 10.0)
        self.assertAlmostEqual(lot.purchase_price, 100.0)
        self.assertEqual(lot.purchase_year, 2020)

        self.assertAlmostEqual(self.manager.get_position_shares("AAPL"), 10.0)
        self.assertAlmostEqual(self.manager.total_cost_basis(), 1000.0)

        # Full sale at $150
        realized_gain, depleted_lots = self.manager.sell_shares(
            ticker="AAPL", shares_to_sell=10.0, current_price=150.0, current_year=2021
        )
        self.assertAlmostEqual(realized_gain, 500.0)
        self.assertEqual(len(depleted_lots), 1)
        self.assertAlmostEqual(depleted_lots[0].shares, 10.0)
        self.assertAlmostEqual(depleted_lots[0].purchase_price, 100.0)

        # Active position should now be zero
        self.assertAlmostEqual(self.manager.get_position_shares("AAPL"), 0.0)
        self.assertAlmostEqual(self.manager.total_cost_basis(), 0.0)
        self.assertNotIn("AAPL", self.manager.get_all_positions())

    def test_multi_lot_fifo_depletion(self):
        """2. Multi-lot FIFO depletion (Lot 1 @ $100, Lot 2 @ $150; Lot 1 depleted first)."""
        lot1 = self.manager.add_lot("AAPL", shares=10.0, price=100.0, year=2019)
        lot2 = self.manager.add_lot("AAPL", shares=10.0, price=150.0, year=2020)

        self.assertAlmostEqual(self.manager.get_position_shares("AAPL"), 20.0)
        self.assertAlmostEqual(self.manager.total_cost_basis(), 2500.0)

        # Sell 12 shares at $200 in 2021
        # Lot 1 (10 shares @ $100 -> cost $1,000) depleted fully
        # Lot 2 (2 shares @ $150 -> cost $300) depleted partially
        # Total cost basis sold = $1,300. Proceeds = 12 * $200 = $2,400.
        # Realized gain = $2,400 - $1,300 = $1,100.
        realized_gain, depleted_lots = self.manager.sell_shares(
            ticker="AAPL", shares_to_sell=12.0, current_price=200.0, current_year=2021
        )
        self.assertAlmostEqual(realized_gain, 1100.0)
        self.assertEqual(len(depleted_lots), 2)

        # Verify depleted lot details
        self.assertAlmostEqual(depleted_lots[0].shares, 10.0)
        self.assertAlmostEqual(depleted_lots[0].purchase_price, 100.0)
        self.assertAlmostEqual(depleted_lots[1].shares, 2.0)
        self.assertAlmostEqual(depleted_lots[1].purchase_price, 150.0)

        # Remaining in Lot 2 = 8 shares @ $150
        self.assertAlmostEqual(self.manager.get_position_shares("AAPL"), 8.0)
        self.assertAlmostEqual(self.manager.total_cost_basis(), 1200.0)

    def test_partial_lot_splitting(self):
        """3. Partial lot splitting (selling 5 of 10 shares leaves 5 shares at original price)."""
        self.manager.add_lot("MSFT", shares=10.0, price=100.0, year=2020)

        realized_gain, depleted_lots = self.manager.sell_shares(
            ticker="MSFT", shares_to_sell=5.0, current_price=120.0, current_year=2021
        )
        # 5 shares * $120 = $600 proceeds - 5 shares * $100 ($500 cost) = $100 gain
        self.assertAlmostEqual(realized_gain, 100.0)
        self.assertEqual(len(depleted_lots), 1)
        self.assertAlmostEqual(depleted_lots[0].shares, 5.0)
        self.assertAlmostEqual(depleted_lots[0].purchase_price, 100.0)

        # Remaining: 5 shares at $100
        self.assertAlmostEqual(self.manager.get_position_shares("MSFT"), 5.0)
        self.assertAlmostEqual(self.manager.total_cost_basis(), 500.0)

    def test_capital_loss_carryforward_netting(self):
        """4. Capital loss carryforward netting:
        Year 1: Net loss of $2,000 -> tax paid = $0, carryforward = $2,000.
        Year 2: Net gain of $3,000 -> nets against $2,000 carryforward -> taxable gain = $1,000,
                tax paid at 30% = $300, carryforward = $0.
        """
        # Year 1 (2020): Buy at $50, sell at $30 (loss of $2,000)
        self.manager.add_lot("XYZ", shares=100.0, price=50.0, year=2020)
        gain_yr1, _ = self.manager.sell_shares("XYZ", shares_to_sell=100.0, current_price=30.0, current_year=2020)
        self.assertAlmostEqual(gain_yr1, -2000.0)

        tax_paid_1, net_taxable_1, carryforward_1 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2020)
        self.assertAlmostEqual(tax_paid_1, 0.0)
        self.assertAlmostEqual(net_taxable_1, -2000.0)
        self.assertAlmostEqual(carryforward_1, 2000.0)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 2000.0)

        # Year 2 (2021): Buy at $10, sell at $40 (gain of $3,000)
        self.manager.add_lot("ABC", shares=100.0, price=10.0, year=2021)
        gain_yr2, _ = self.manager.sell_shares("ABC", shares_to_sell=100.0, current_price=40.0, current_year=2021)
        self.assertAlmostEqual(gain_yr2, 3000.0)

        tax_paid_2, net_taxable_2, carryforward_2 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2021)
        self.assertAlmostEqual(tax_paid_2, 300.0)
        self.assertAlmostEqual(net_taxable_2, 1000.0)
        self.assertAlmostEqual(carryforward_2, 0.0)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 0.0)

    def test_capital_loss_carryforward_partial_exhaustion(self):
        """5. Capital loss carryforward partial exhaustion:
        Year 1: Net loss of $5,000 -> carryforward = $5,000.
        Year 2: Net gain of $1,000 -> tax paid = $0, remaining carryforward = $4,000.
        """
        # Year 1: Loss of $5,000
        self.manager.add_lot("LOSER", shares=100.0, price=100.0, year=2020)
        self.manager.sell_shares("LOSER", shares_to_sell=100.0, current_price=50.0, current_year=2020)

        tax_paid_1, net_taxable_1, carryforward_1 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2020)
        self.assertAlmostEqual(tax_paid_1, 0.0)
        self.assertAlmostEqual(net_taxable_1, -5000.0)
        self.assertAlmostEqual(carryforward_1, 5000.0)

        # Year 2: Gain of $1,000
        self.manager.add_lot("WINNER", shares=100.0, price=10.0, year=2021)
        self.manager.sell_shares("WINNER", shares_to_sell=100.0, current_price=20.0, current_year=2021)

        tax_paid_2, net_taxable_2, carryforward_2 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2021)
        self.assertAlmostEqual(tax_paid_2, 0.0)
        self.assertAlmostEqual(net_taxable_2, -4000.0)
        self.assertAlmostEqual(carryforward_2, 4000.0)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 4000.0)

    def test_unrealized_gain_calculation(self):
        """6. Embedded unrealized gain calculation for terminal liquidation."""
        self.manager.add_lot("AAPL", shares=10.0, price=100.0, year=2020)  # cost = 1000
        self.manager.add_lot("MSFT", shares=20.0, price=200.0, year=2021)  # cost = 4000
        self.assertAlmostEqual(self.manager.total_cost_basis(), 5000.0)

        current_prices = {
            "AAPL": 150.0,  # value = 1500, gain = 500
            "MSFT": 250.0,  # value = 5000, gain = 1000
        }
        unrealized = self.manager.get_unrealized_gain(current_prices)
        self.assertAlmostEqual(unrealized, 1500.0)

    def test_oversell_prevention(self):
        """7. Oversell prevention (attempting to sell more shares than held raises ValueError)."""
        self.manager.add_lot("GOOG", shares=10.0, price=100.0, year=2020)

        # Selling 10.5 shares exceeds 10.0 by more than epsilon -> ValueError
        with self.assertRaises(ValueError):
            self.manager.sell_shares("GOOG", shares_to_sell=10.5, current_price=120.0, current_year=2021)

        # Selling ticker not held -> ValueError
        with self.assertRaises(ValueError):
            self.manager.sell_shares("NVDA", shares_to_sell=1.0, current_price=50.0, current_year=2021)

        # Selling with tiny epsilon (1e-8) overshoot should be tolerated and capped to held shares
        gain, depleted = self.manager.sell_shares(
            "GOOG", shares_to_sell=10.0 + 1e-8, current_price=120.0, current_year=2021
        )
        self.assertAlmostEqual(gain, 200.0)
        self.assertAlmostEqual(self.manager.get_position_shares("GOOG"), 0.0)

    def test_consecutive_multi_year_losses_accumulate(self):
        """Edge case: Multiple loss years consecutively compound carryforward."""
        # Year 1: loss of $1,000
        self.manager.add_lot("S1", 10.0, 100.0, 2020)
        self.manager.sell_shares("S1", 10.0, 0.0, 2020)
        self.manager.settle_annual_taxes(0.30, 2020)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 1000.0)

        # Year 2: additional loss of $2,000
        self.manager.add_lot("S2", 20.0, 100.0, 2021)
        self.manager.sell_shares("S2", 20.0, 0.0, 2021)
        self.manager.settle_annual_taxes(0.30, 2021)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 3000.0)

    def test_zero_tax_rate_settlement(self):
        """Edge case: Zero tax rate (pre-tax simulation) pays 0 tax but resets carryforward on net gain."""
        self.manager.add_lot("T", 10.0, 100.0, 2020)
        self.manager.sell_shares("T", 10.0, 200.0, 2020)
        tax_paid, net_gain, carryforward = self.manager.settle_annual_taxes(0.0, 2020)
        self.assertAlmostEqual(tax_paid, 0.0)
        self.assertAlmostEqual(net_gain, 1000.0)
        self.assertAlmostEqual(carryforward, 0.0)

    def test_get_all_positions_filtering(self):
        """Positions map only includes tickers with active shares."""
        self.manager.add_lot("A", 10.0, 50.0, 2020)
        self.manager.add_lot("B", 20.0, 30.0, 2020)
        self.manager.sell_shares("A", 10.0, 60.0, 2020)

        positions = self.manager.get_all_positions()
        self.assertNotIn("A", positions)
        self.assertIn("B", positions)
        self.assertAlmostEqual(positions["B"], 20.0)

    def test_zero_shares_sell(self):
        """Selling 0 shares is a no-op."""
        self.manager.add_lot("A", 10.0, 50.0, 2020)
        gain, depleted = self.manager.sell_shares("A", 0.0, 60.0, 2020)
        self.assertAlmostEqual(gain, 0.0)
        self.assertEqual(len(depleted), 0)
        self.assertAlmostEqual(self.manager.get_position_shares("A"), 10.0)


if __name__ == "__main__":
    unittest.main()
