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

    def test_adjust_basis_ratio_multi_lot(self):
        """Adjust basis ratio across multiple lots preserving shares and acquisition dates."""
        manager = FIFOTaxLotManager()
        manager.add_lot("MO", 100.0, 50.0, 2005)
        manager.add_lot("MO", 50.0, 60.0, 2006)

        # 2007 Kraft spinoff: ratio 0.6910
        manager.adjust_basis_ratio("MO", 0.6910)

        lots = manager.get_lots("MO")
        self.assertEqual(len(lots), 2)
        self.assertAlmostEqual(lots[0].purchase_price, 34.55, places=2)
        self.assertAlmostEqual(lots[1].purchase_price, 41.46, places=2)
        self.assertEqual(lots[0].shares, 100.0)
        self.assertEqual(lots[1].shares, 50.0)
        self.assertEqual(lots[0].year, 2005)

    def test_adjust_basis_ratio_preserves_attributes_and_edge_cases(self):
        """Preserves quarter, cost_basis_per_share property, handles missing ticker, copy isolation."""
        manager = FIFOTaxLotManager()
        lot = manager.add_lot("MO", 100.0, 50.0, 2005, quarter=1)
        self.assertEqual(lot.cost_basis_per_share, 50.0)
        self.assertEqual(lot.quarter, 1)

        # Spinoff ratio adjustment
        manager.adjust_basis_ratio("MO", 0.6910)
        self.assertEqual(lot.cost_basis_per_share, 34.55)
        self.assertEqual(lot.quarter, 1)
        self.assertEqual(lot.shares, 100.0)

        # Missing ticker adjustment should be a safe no-op
        manager.adjust_basis_ratio("UNKNOWN", 0.5)

        # get_lots on non-existent ticker returns empty list
        self.assertEqual(manager.get_lots("UNKNOWN"), [])

        # get_lots returns a copy of the list
        lots_copy = manager.get_lots("MO")
        lots_copy.clear()
        self.assertEqual(len(manager.get_lots("MO")), 1)

    def test_adjust_basis_ratio_with_capital_gains_realization(self):
        """Verify child share monetization calculates child basis, realizes gain, and taxes at 30%."""
        manager = FIFOTaxLotManager()
        manager.add_lot("PARENT", 1.0, 100.0, 2020)

        # Spinoff: ratio 0.80, gross proceeds = $40.0
        # Parent basis: 100 * 0.80 = $80.0
        # Child basis: 100 * (1 - 0.80) = $20.0
        # Realized gain on child sale: $40 - $20 = $20.0
        child_gain = manager.adjust_basis_ratio("PARENT", 0.80, gross_proceeds=40.0)
        self.assertAlmostEqual(child_gain, 20.0)
        self.assertAlmostEqual(manager.current_annual_realized_gain, 20.0)

        # Lots updated
        lots = manager.get_lots("PARENT")
        self.assertEqual(len(lots), 1)
        self.assertAlmostEqual(lots[0].purchase_price, 80.0)

        # Tax settlement at 30%
        tax_paid, net_taxable, loss_cf = manager.settle_annual_taxes(0.30, 2020)
        self.assertAlmostEqual(net_taxable, 20.0)
        self.assertAlmostEqual(tax_paid, 6.0)
        self.assertAlmostEqual(loss_cf, 0.0)

        # Terminal liquidation of parent at $160
        # Gain on parent = 160 - 80 = $80; tax = $80 * 0.30 = $24
        # Total wealth: ($40 proceeds - $6 tax) + ($160 parent - $24 tax) = $34 + $136 = $170.0
        # (Prior buggy engine gave $176 because $20 child gain was never taxed)
        parent_gain, _ = manager.sell_shares("PARENT", 1.0, 160.0, 2021)
        self.assertAlmostEqual(parent_gain, 80.0)
        term_tax, _, _ = manager.settle_annual_taxes(0.30, 2021)
        self.assertAlmostEqual(term_tax, 24.0)
        total_tax = tax_paid + term_tax
        self.assertAlmostEqual(total_tax, 30.0)

    def test_gain_then_loss_intra_year_netting(self):
        """Gain followed by loss in same year reconciles earlier tax payment with refund and zero carryforward."""
        # Q1/Q2: Realize +$100 gain
        self.manager.add_lot("WIN", shares=10.0, price=10.0, year=2020, quarter=1)
        self.manager.sell_shares("WIN", shares_to_sell=10.0, current_price=20.0, current_year=2020, current_quarter=2)
        tax_delta_1, net_1, cf_1 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2020)
        self.assertAlmostEqual(tax_delta_1, 30.0)
        self.assertAlmostEqual(net_1, 100.0)
        self.assertAlmostEqual(cf_1, 0.0)

        # Q3: Realize -$100 loss in same calendar year
        self.manager.add_lot("LOSE", shares=10.0, price=20.0, year=2020, quarter=3)
        self.manager.sell_shares("LOSE", shares_to_sell=10.0, current_price=10.0, current_year=2020, current_quarter=3)
        tax_delta_2, net_2, cf_2 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2020)
        # Should refund -$30.0, net annual gain becomes 0.0, loss carryforward becomes 0.0
        self.assertAlmostEqual(tax_delta_2, -30.0)
        self.assertAlmostEqual(net_2, 0.0)
        self.assertAlmostEqual(cf_2, 0.0)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 0.0)

        total_annual_tax = tax_delta_1 + tax_delta_2
        self.assertAlmostEqual(total_annual_tax, 0.0)

    def test_gain_then_partial_loss_intra_year_netting(self):
        """Gain followed by partial loss in same year refunds corresponding portion of tax."""
        # Gain of $100
        self.manager.add_lot("WIN", shares=10.0, price=10.0, year=2020)
        self.manager.sell_shares("WIN", shares_to_sell=10.0, current_price=20.0, current_year=2020)
        tax_delta_1, _, _ = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2020)
        self.assertAlmostEqual(tax_delta_1, 30.0)

        # Loss of $40 in same year
        self.manager.add_lot("LOSE", shares=10.0, price=20.0, year=2020)
        self.manager.sell_shares("LOSE", shares_to_sell=10.0, current_price=16.0, current_year=2020)
        tax_delta_2, net_2, cf_2 = self.manager.settle_annual_taxes(tax_rate=0.30, current_year=2020)
        # Net annual taxable gain is 60.0; cumulative tax liability is 18.0; delta is 18.0 - 30.0 = -12.0
        self.assertAlmostEqual(tax_delta_2, -12.0)
        self.assertAlmostEqual(net_2, 60.0)
        self.assertAlmostEqual(cf_2, 0.0)
        self.assertAlmostEqual(tax_delta_1 + tax_delta_2, 18.0)

    def test_loss_then_gain_symmetry(self):
        """Verify identical annual tax ($0) and carryforward ($0) whether loss or gain occurs first."""
        # Sequence A: Gain +100 then Loss -100
        mgr_a = FIFOTaxLotManager()
        mgr_a.add_lot("A1", 10.0, 10.0, 2020)
        mgr_a.sell_shares("A1", 10.0, 20.0, 2020)
        t_a1, _, _ = mgr_a.settle_annual_taxes(0.30, 2020)
        mgr_a.add_lot("A2", 10.0, 20.0, 2020)
        mgr_a.sell_shares("A2", 10.0, 10.0, 2020)
        t_a2, net_a, cf_a = mgr_a.settle_annual_taxes(0.30, 2020)

        # Sequence B: Loss -100 then Gain +100
        mgr_b = FIFOTaxLotManager()
        mgr_b.add_lot("B1", 10.0, 20.0, 2020)
        mgr_b.sell_shares("B1", 10.0, 10.0, 2020)
        t_b1, _, _ = mgr_b.settle_annual_taxes(0.30, 2020)
        mgr_b.add_lot("B2", 10.0, 10.0, 2020)
        mgr_b.sell_shares("B2", 10.0, 20.0, 2020)
        t_b2, net_b, cf_b = mgr_b.settle_annual_taxes(0.30, 2020)

        # Both sequences must arrive at identical calendar-year totals
        self.assertAlmostEqual(t_a1 + t_a2, t_b1 + t_b2)
        self.assertAlmostEqual(t_a1 + t_a2, 0.0)
        self.assertAlmostEqual(net_a, net_b)
        self.assertAlmostEqual(cf_a, cf_b)
        self.assertAlmostEqual(cf_a, 0.0)

    def test_spinoff_gain_nets_with_subsequent_loss_intra_year(self):
        """Spinoff child monetization gain in Q1 followed by sale loss in Q2 nets to zero."""
        manager = FIFOTaxLotManager()
        manager.add_lot("PARENT", 1.0, 100.0, 2020)
        # Spinoff realization: $40 proceeds - $20 child basis = $20 child gain
        manager.adjust_basis_ratio("PARENT", 0.80, gross_proceeds=40.0, current_year=2020)
        t1, net1, cf1 = manager.settle_annual_taxes(0.30, 2020)
        self.assertAlmostEqual(t1, 6.0)
        self.assertAlmostEqual(net1, 20.0)

        # Subsequent trade loss of -$20 in same year
        manager.add_lot("LOSE", 10.0, 20.0, 2020)
        manager.sell_shares("LOSE", 10.0, 18.0, 2020)
        t2, net2, cf2 = manager.settle_annual_taxes(0.30, 2020)
        self.assertAlmostEqual(t2, -6.0)
        self.assertAlmostEqual(net2, 0.0)
        self.assertAlmostEqual(cf2, 0.0)
        self.assertAlmostEqual(t1 + t2, 0.0)

    def test_year_rollover_prevents_loss_carryback(self):
        """Loss in year 2 does not carry back to refund taxes paid in year 1."""
        # Year 1 (2020): Gain +$100 pays $30 tax
        self.manager.add_lot("Y1", 10.0, 10.0, 2020)
        self.manager.sell_shares("Y1", 10.0, 20.0, 2020)
        t1, net1, cf1 = self.manager.settle_annual_taxes(0.30, 2020)
        self.assertAlmostEqual(t1, 30.0)
        self.assertAlmostEqual(cf1, 0.0)

        # Year 2 (2021): Loss -$100 pays $0 tax and creates $100 carryforward
        self.manager.add_lot("Y2", 10.0, 20.0, 2021)
        self.manager.sell_shares("Y2", 10.0, 10.0, 2021)
        t2, net2, cf2 = self.manager.settle_annual_taxes(0.30, 2021)
        self.assertAlmostEqual(t2, 0.0)  # Must NOT be -30.0! (No carryback)
        self.assertAlmostEqual(net2, -100.0)
        self.assertAlmostEqual(cf2, 100.0)
        self.assertAlmostEqual(self.manager.capital_loss_carryforward, 100.0)


if __name__ == "__main__":
    unittest.main()

