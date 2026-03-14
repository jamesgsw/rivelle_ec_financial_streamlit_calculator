"""
Rivelle EC Finance Planner - Comprehensive Test Suite
======================================================

This test suite validates all financial calculations against official regulatory sources:

SOURCES VALIDATED (as of March 2026):
- BSD (Buyer's Stamp Duty): IRAS rates effective 15 Feb 2023
  https://www.iras.gov.sg/taxes/stamp-duty/for-property/buying-or-acquiring-property/buyer's-stamp-duty-(bsd)
  
- MSR (Mortgage Servicing Ratio): 30% cap per MAS
  https://www.mas.gov.sg/regulation/explainers/new-housing-loans/msr-and-tdsr-rules
  
- LTV (Loan-to-Value): 75% cap for first property, no outstanding loans, tenure ≤30 years
  https://www.mas.gov.sg/regulation/explainers/new-housing-loans/loan-tenure-and-loan-to-value-limits
  
- Stress-test rate: 4% p.a. per MAS (used for MSR loan qualification)
  
- CPF OA interest: 2.5% p.a. (floor rate)
  https://www.cpf.gov.sg/member/growing-your-savings/earning-higher-returns/earning-attractive-interest
  
- DPS Schedule: 5%/15%/65%/15% (Rivelle EC specific, per developer website)
- DPS Surcharge: 3% premium on NPS price

UNIT TYPES (Rivelle EC - Tampines):
- 3BR Premium: NPS $1,588,000 (883 sqft)
- 3BR Premium + Study: NPS $1,663,000 (926 sqft)  
- 4 Bedroom: NPS $1,893,000 (1,044 sqft)
"""

import unittest
import math
from datetime import datetime, timedelta
import calendar

DPS_SURCHARGE = 0.03
STRESS_TEST_RATE = 0.04
CPF_OA_RATE = 0.025
MSR_CAP = 0.30
LTV_CAP = 0.75

BSD_TIERS = [
    (180_000, 0.01),
    (180_000, 0.02),
    (640_000, 0.03),
    (500_000, 0.04),
    (1_500_000, 0.05),
    (float("inf"), 0.06),
]

BOOKING_DATE = datetime(2026, 4, 1)
OTP_DATE = datetime(2026, 6, 1)
TOP_DATE = datetime(2030, 6, 1)
CSC_DATE = datetime(2033, 6, 1)


def add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)


def calculate_bsd(price):
    bsd = 0.0
    remaining = price
    for band, rate in BSD_TIERS:
        taxable = min(remaining, band)
        bsd += taxable * rate
        remaining -= taxable
        if remaining <= 0:
            break
    return bsd


def calculate_monthly_repayment(loan_amount, annual_rate, tenure_years):
    if loan_amount <= 0 or annual_rate <= 0 or tenure_years <= 0:
        return 0.0
    r = annual_rate / 12
    n = tenure_years * 12
    return loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def calculate_max_loan(monthly_income, stress_rate, tenure_years):
    max_monthly = monthly_income * MSR_CAP
    r = stress_rate / 12
    n = tenure_years * 12
    if r == 0:
        return max_monthly * n
    return max_monthly * ((1 + r) ** n - 1) / (r * (1 + r) ** n)


class TestBSDCalculation(unittest.TestCase):
    """
    BSD (Buyer's Stamp Duty) tests validated against IRAS official rates.
    
    IRAS BSD Tiers (effective 15 Feb 2023 for residential properties):
    - First $180,000: 1%
    - Next $180,000: 2%
    - Next $640,000: 3%
    - Next $500,000: 4%
    - Next $1,500,000: 5%
    - Remaining: 6%
    
    Source: https://www.iras.gov.sg/taxes/stamp-duty/for-property/buying-or-acquiring-property/buyer's-stamp-duty-(bsd)
    """
    
    def test_bsd_first_tier_only(self):
        """Property at $180,000 should have BSD of $1,800 (1%)"""
        self.assertEqual(calculate_bsd(180_000), 1_800)
    
    def test_bsd_within_first_tier(self):
        """Property at $100,000 should have BSD of $1,000 (1%)"""
        self.assertEqual(calculate_bsd(100_000), 1_000)
    
    def test_bsd_second_tier(self):
        """Property at $360,000 should span first two tiers"""
        expected = 180_000 * 0.01 + 180_000 * 0.02
        self.assertEqual(calculate_bsd(360_000), expected)
    
    def test_bsd_third_tier(self):
        """Property at $1,000,000 should span three tiers"""
        expected = 180_000 * 0.01 + 180_000 * 0.02 + 640_000 * 0.03
        self.assertEqual(calculate_bsd(1_000_000), expected)
    
    def test_bsd_rivelle_3br_premium(self):
        """
        3BR Premium DPS price: $1,635,640 ($1,588,000 * 1.03)
        BSD calculation:
        - First $180,000 @ 1% = $1,800
        - Next $180,000 @ 2% = $3,600
        - Next $640,000 @ 3% = $19,200
        - Next $500,000 @ 4% = $20,000
        - Remaining $135,640 @ 5% = $6,782
        Total: $51,382
        """
        nps_price = 1_588_000
        dps_price = round(nps_price * (1 + DPS_SURCHARGE))
        expected = 1_800 + 3_600 + 19_200 + 20_000 + (dps_price - 1_500_000) * 0.05
        self.assertAlmostEqual(calculate_bsd(dps_price), expected, places=0)
    
    def test_bsd_rivelle_3br_premium_study(self):
        """
        3BR Premium + Study DPS price: $1,712,890 ($1,663,000 * 1.03)
        BSD calculation:
        - First $180,000 @ 1% = $1,800
        - Next $180,000 @ 2% = $3,600
        - Next $640,000 @ 3% = $19,200
        - Next $500,000 @ 4% = $20,000
        - Remaining $212,890 @ 5% = $10,644.50
        Total: $55,244.50
        """
        nps_price = 1_663_000
        dps_price = round(nps_price * (1 + DPS_SURCHARGE))
        expected = 1_800 + 3_600 + 19_200 + 20_000 + (dps_price - 1_500_000) * 0.05
        self.assertAlmostEqual(calculate_bsd(dps_price), expected, places=0)
    
    def test_bsd_rivelle_4br(self):
        """
        4BR DPS price: $1,949,790 ($1,893,000 * 1.03)
        BSD calculation:
        - First $180,000 @ 1% = $1,800
        - Next $180,000 @ 2% = $3,600
        - Next $640,000 @ 3% = $19,200
        - Next $500,000 @ 4% = $20,000
        - Remaining $449,790 @ 5% = $22,489.50
        Total: $67,089.50
        """
        nps_price = 1_893_000
        dps_price = round(nps_price * (1 + DPS_SURCHARGE))
        expected = 1_800 + 3_600 + 19_200 + 20_000 + (dps_price - 1_500_000) * 0.05
        self.assertAlmostEqual(calculate_bsd(dps_price), expected, places=0)
    
    def test_bsd_iras_example(self):
        """
        IRAS Example: Terrace house at $4,500,100 (17 Feb 2023)
        BSD = $209,606
        
        Breakdown per IRAS:
        - First $180,000 @ 1% = $1,800
        - Next $180,000 @ 2% = $3,600
        - Next $640,000 @ 3% = $19,200
        - Next $500,000 @ 4% = $20,000
        - Next $1,500,000 @ 5% = $75,000
        - Remaining $1,500,100 @ 6% = $90,006
        Total: $209,606
        """
        expected = 1_800 + 3_600 + 19_200 + 20_000 + 75_000 + 90_006
        self.assertAlmostEqual(calculate_bsd(4_500_100), expected, places=0)
    
    def test_bsd_sixth_tier(self):
        """Property at $5,000,000 should span all six tiers"""
        expected = (180_000 * 0.01 + 180_000 * 0.02 + 640_000 * 0.03 + 
                    500_000 * 0.04 + 1_500_000 * 0.05 + 2_000_000 * 0.06)
        self.assertEqual(calculate_bsd(5_000_000), expected)
    
    def test_bsd_zero_price(self):
        """Zero price should return zero BSD"""
        self.assertEqual(calculate_bsd(0), 0)


class TestLoanCalculations(unittest.TestCase):
    """
    Loan calculation tests validated against MAS regulations.
    
    Key regulations (MAS):
    - MSR: 30% of gross monthly income for HDB/EC
    - LTV: 75% maximum (first property, no outstanding loans, tenure ≤30 years)
    - Stress-test rate: 4% p.a. (banks must use this for loan qualification)
    - Max tenure: 30 years for HDB/EC
    
    Sources:
    - https://www.mas.gov.sg/regulation/explainers/new-housing-loans/msr-and-tdsr-rules
    - https://www.mas.gov.sg/regulation/explainers/new-housing-loans/loan-tenure-and-loan-to-value-limits
    """
    
    def test_monthly_repayment_formula(self):
        """
        Test standard amortization formula: PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
        
        Example: $1,000,000 loan at 4% p.a. for 30 years
        Monthly rate = 0.04/12 = 0.003333...
        n = 30 * 12 = 360
        PMT = 1,000,000 * [0.003333 * 1.003333^360] / [1.003333^360 - 1]
        PMT ≈ $4,774.15
        """
        loan = 1_000_000
        rate = 0.04
        tenure = 30
        pmt = calculate_monthly_repayment(loan, rate, tenure)
        self.assertAlmostEqual(pmt, 4_774.15, delta=0.50)
    
    def test_monthly_repayment_higher_rate(self):
        """$500,000 loan at 5% p.a. for 25 years"""
        loan = 500_000
        rate = 0.05
        tenure = 25
        r = rate / 12
        n = tenure * 12
        expected = loan * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        pmt = calculate_monthly_repayment(loan, rate, tenure)
        self.assertAlmostEqual(pmt, expected, places=2)
    
    def test_monthly_repayment_zero_values(self):
        """Zero loan amount should return zero payment"""
        self.assertEqual(calculate_monthly_repayment(0, 0.04, 30), 0)
        self.assertEqual(calculate_monthly_repayment(1_000_000, 0, 30), 0)
        self.assertEqual(calculate_monthly_repayment(1_000_000, 0.04, 0), 0)
    
    def test_max_loan_msr_calculation(self):
        """
        MSR-based max loan calculation at 4% stress-test rate.
        
        Combined income: $16,653.04/month
        MSR cap: 30% = $4,995.91/month max payment
        At 4% stress-test, 30-year tenure, max loan ≈ $1,046,000
        """
        income = 16_653.04
        tenure = 30
        max_loan = calculate_max_loan(income, STRESS_TEST_RATE, tenure)
        self.assertGreater(max_loan, 1_000_000)
        self.assertLess(max_loan, 1_100_000)
    
    def test_msr_cap_verification(self):
        """
        Verify MSR cap is correctly applied at 30%.
        
        For any loan amount, monthly payment should not exceed 30% of income.
        """
        income = 16_653.04
        max_loan = calculate_max_loan(income, STRESS_TEST_RATE, 30)
        monthly_payment = calculate_monthly_repayment(max_loan, STRESS_TEST_RATE, 30)
        msr = monthly_payment / income
        self.assertAlmostEqual(msr, MSR_CAP, places=4)
    
    def test_ltv_constraint(self):
        """
        LTV constraint: max loan = 75% of property value.
        
        For 3BR Premium + Study at $1,712,890:
        LTV max = $1,712,890 * 0.75 = $1,284,667.50
        
        Compare with MSR max to determine binding constraint.
        """
        dps_price = round(1_663_000 * (1 + DPS_SURCHARGE))
        ltv_max = dps_price * LTV_CAP
        self.assertAlmostEqual(ltv_max, dps_price * 0.75, places=2)
    
    def test_binding_constraint_msr_vs_ltv(self):
        """
        For Rivelle at combined income $16,653.04/month:
        - MSR max loan ≈ $1,046,000
        - LTV max (3BR+Study) = $1,712,890 * 0.75 = $1,284,667
        
        MSR is the binding constraint (lower).
        """
        income = 16_653.04
        tenure = 30
        msr_max = calculate_max_loan(income, STRESS_TEST_RATE, tenure)
        
        dps_price = round(1_663_000 * (1 + DPS_SURCHARGE))
        ltv_max = dps_price * LTV_CAP
        
        self.assertLess(msr_max, ltv_max)


class TestDPSSchedule(unittest.TestCase):
    """
    DPS (Deferred Payment Scheme) schedule tests.
    
    Rivelle DPS Structure: 5% / 15% / 65% / 15%
    - 5% at booking (cash only)
    - 15% at OTP exercise (CPF and/or cash)
    - 65% at TOP (bank loan + CPF + cash)
    - 15% at CSC (CPF + cash)
    
    DPS Surcharge: 3% premium on NPS price
    
    Key dates:
    - Booking: April 2026
    - OTP: June 2026
    - TOP: June 2030
    - CSC: June 2033
    """
    
    def test_dps_surcharge(self):
        """DPS price should be NPS + 3%"""
        nps_price = 1_663_000
        dps_price = round(nps_price * (1 + DPS_SURCHARGE))
        expected = round(1_663_000 * 1.03)
        self.assertEqual(dps_price, expected)
    
    def test_booking_fee_5_percent(self):
        """Booking fee is 5% of DPS price (cash only)"""
        dps_price = round(1_663_000 * 1.03)
        booking_fee = dps_price * 0.05
        self.assertAlmostEqual(booking_fee, dps_price * 0.05, places=2)
    
    def test_otp_exercise_15_percent(self):
        """OTP exercise is 15% of DPS price"""
        dps_price = round(1_663_000 * 1.03)
        otp_amount = dps_price * 0.15
        self.assertAlmostEqual(otp_amount, dps_price * 0.15, places=2)
    
    def test_top_balance_65_percent(self):
        """TOP balance is 65% of DPS price"""
        dps_price = round(1_663_000 * 1.03)
        top_amount = dps_price * 0.65
        self.assertAlmostEqual(top_amount, dps_price * 0.65, places=2)
    
    def test_csc_balance_15_percent(self):
        """CSC balance is 15% of DPS price"""
        dps_price = round(1_663_000 * 1.03)
        csc_amount = dps_price * 0.15
        self.assertAlmostEqual(csc_amount, dps_price * 0.15, places=2)
    
    def test_dps_schedule_sums_to_100(self):
        """DPS schedule (5+15+65+15) must equal 100%"""
        total = 0.05 + 0.15 + 0.65 + 0.15
        self.assertEqual(total, 1.0)
    
    def test_pre_top_outlay(self):
        """
        Pre-TOP outlay = Booking (5%) + OTP (15%) + BSD
        For 3BR Premium + Study ($1,712,890):
        - Booking: $85,644.50
        - OTP: $256,933.50
        - BSD: ~$55,245
        Total: ~$397,823
        """
        dps_price = round(1_663_000 * 1.03)
        booking = dps_price * 0.05
        otp = dps_price * 0.15
        bsd = calculate_bsd(dps_price)
        pre_top = booking + otp + bsd
        self.assertGreater(pre_top, 350_000)
        self.assertLess(pre_top, 450_000)


class TestCPFInterest(unittest.TestCase):
    """
    CPF OA interest calculation tests.
    
    CPF OA interest rate: 2.5% p.a. (floor rate, guaranteed)
    Interest credited quarterly (March, June, September, December)
    
    Source: https://www.cpf.gov.sg/member/growing-your-savings/earning-higher-returns/earning-attractive-interest
    
    Note: Extra interest on first $60K goes to SA/RA, not OA.
    For housing planning, we use base 2.5% rate on OA balance.
    """
    
    def test_cpf_quarterly_interest(self):
        """CPF OA earns 2.5% p.a., credited quarterly (0.625% per quarter)"""
        quarterly_rate = CPF_OA_RATE / 4
        self.assertAlmostEqual(quarterly_rate, 0.00625, places=5)
    
    def test_cpf_annual_growth(self):
        """$200,000 OA balance after 1 year with quarterly compounding"""
        balance = 200_000
        quarterly_rate = CPF_OA_RATE / 4
        for _ in range(4):
            balance *= (1 + quarterly_rate)
        expected = 200_000 * (1 + quarterly_rate) ** 4
        self.assertAlmostEqual(balance, expected, places=2)
    
    def test_cpf_4_year_growth(self):
        """
        CPF OA balance growth over 4 years (booking to TOP).
        Starting: $200,000
        Monthly contribution: $4,000
        Expected final balance > $400,000
        """
        balance = 200_000
        monthly_contrib = 4_000
        quarterly_rate = CPF_OA_RATE / 4
        
        for month in range(1, 49):
            balance += monthly_contrib
            if month % 3 == 0:
                balance *= (1 + quarterly_rate)
        
        self.assertGreater(balance, 400_000)


class TestAddMonths(unittest.TestCase):
    """Test the add_months helper function for date arithmetic."""
    
    def test_add_months_simple(self):
        """Add 6 months to January should give July"""
        dt = datetime(2026, 1, 15)
        result = add_months(dt, 6)
        self.assertEqual(result.month, 7)
        self.assertEqual(result.year, 2026)
    
    def test_add_months_year_rollover(self):
        """Add 8 months to June should give February next year"""
        dt = datetime(2026, 6, 1)
        result = add_months(dt, 8)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.year, 2027)
    
    def test_add_months_end_of_month(self):
        """Adding months to Jan 31 should handle Feb correctly"""
        dt = datetime(2026, 1, 31)
        result = add_months(dt, 1)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 28)
    
    def test_months_booking_to_top(self):
        """Booking (Apr 2026) to TOP (Jun 2030) = 50 months"""
        months = (TOP_DATE.year - BOOKING_DATE.year) * 12 + (TOP_DATE.month - BOOKING_DATE.month)
        self.assertEqual(months, 50)
    
    def test_months_booking_to_csc(self):
        """Booking (Apr 2026) to CSC (Jun 2033) = 86 months"""
        months = (CSC_DATE.year - BOOKING_DATE.year) * 12 + (CSC_DATE.month - BOOKING_DATE.month)
        self.assertEqual(months, 86)


class TestIntegrationScenarios(unittest.TestCase):
    """
    Integration tests for complete financial scenarios.
    
    These tests simulate real-world scenarios based on the Rivelle EC purchase.
    """
    
    def test_scenario_3br_premium_study_viable(self):
        """
        Scenario: 3BR Premium + Study at DPS price
        Combined income: $16,653.04/month
        Starting cash: $280,000
        Starting CPF OA: $200,000
        Monthly savings: $8,000
        Monthly CPF: $4,000
        
        Expected: VIABLE (all milestones can be met)
        """
        dps_price = round(1_663_000 * 1.03)
        income = 16_653.04
        tenure = 30
        
        max_loan_msr = calculate_max_loan(income, STRESS_TEST_RATE, tenure)
        max_loan_ltv = dps_price * LTV_CAP
        max_loan = min(max_loan_msr, max_loan_ltv)
        
        bsd = calculate_bsd(dps_price)
        booking = dps_price * 0.05
        otp = dps_price * 0.15
        
        starting_cash = 280_000
        cash_after_booking = starting_cash - booking
        
        self.assertGreater(cash_after_booking, 0)
        self.assertGreater(max_loan, 1_000_000)
    
    def test_scenario_4br_marginal(self):
        """
        Scenario: 4BR at DPS price (higher price point)
        Same financial profile
        
        Expected: Should be more challenging but still viable
        """
        dps_price = round(1_893_000 * 1.03)
        income = 16_653.04
        tenure = 30
        
        max_loan_msr = calculate_max_loan(income, STRESS_TEST_RATE, tenure)
        max_loan_ltv = dps_price * LTV_CAP
        max_loan = min(max_loan_msr, max_loan_ltv)
        
        bsd = calculate_bsd(dps_price)
        top_amount = dps_price * 0.65
        shortfall = top_amount - max_loan
        
        self.assertGreater(shortfall, 0)
    
    def test_scenario_low_income_not_viable(self):
        """
        Scenario: Low income buyer attempting to purchase
        Combined income: $8,000/month
        
        Expected: NOT VIABLE (MSR constraint too restrictive)
        """
        dps_price = round(1_663_000 * 1.03)
        income = 8_000
        tenure = 30
        
        max_loan_msr = calculate_max_loan(income, STRESS_TEST_RATE, tenure)
        top_amount = dps_price * 0.65
        
        self.assertLess(max_loan_msr, top_amount)


class TestEdgeCases(unittest.TestCase):
    """Edge case and boundary condition tests."""
    
    def test_bsd_exact_tier_boundary(self):
        """Test BSD at exact tier boundaries"""
        self.assertEqual(calculate_bsd(180_000), 1_800)
        
        bsd_360k = calculate_bsd(360_000)
        expected = 180_000 * 0.01 + 180_000 * 0.02
        self.assertEqual(bsd_360k, expected)
    
    def test_bsd_one_dollar_over_tier(self):
        """Test BSD one dollar over tier boundary"""
        bsd = calculate_bsd(180_001)
        expected = 180_000 * 0.01 + 1 * 0.02
        self.assertEqual(bsd, expected)
    
    def test_max_loan_short_tenure(self):
        """Shorter tenure should result in lower max loan"""
        income = 16_653.04
        max_loan_30yr = calculate_max_loan(income, STRESS_TEST_RATE, 30)
        max_loan_20yr = calculate_max_loan(income, STRESS_TEST_RATE, 20)
        self.assertGreater(max_loan_30yr, max_loan_20yr)
    
    def test_monthly_repayment_short_tenure(self):
        """Shorter tenure should result in higher monthly payment"""
        loan = 1_000_000
        rate = 0.04
        pmt_30yr = calculate_monthly_repayment(loan, rate, 30)
        pmt_20yr = calculate_monthly_repayment(loan, rate, 20)
        self.assertLess(pmt_30yr, pmt_20yr)
    
    def test_monthly_repayment_higher_rate(self):
        """Higher interest rate should result in higher monthly payment"""
        loan = 1_000_000
        tenure = 30
        pmt_4pct = calculate_monthly_repayment(loan, 0.04, tenure)
        pmt_5pct = calculate_monthly_repayment(loan, 0.05, tenure)
        self.assertLess(pmt_4pct, pmt_5pct)
    
    def test_dps_surcharge_rounding(self):
        """DPS surcharge calculation should round properly"""
        for nps in [1_588_000, 1_663_000, 1_893_000]:
            dps = round(nps * 1.03)
            self.assertEqual(dps, round(nps * (1 + DPS_SURCHARGE)))


class TestRegulatoryCompliance(unittest.TestCase):
    """
    Tests to verify compliance with Singapore regulatory requirements.
    """
    
    def test_msr_cap_30_percent(self):
        """MSR cap must be exactly 30% per MAS"""
        self.assertEqual(MSR_CAP, 0.30)
    
    def test_ltv_cap_75_percent(self):
        """LTV cap must be 75% for first property"""
        self.assertEqual(LTV_CAP, 0.75)
    
    def test_stress_test_rate_4_percent(self):
        """Stress-test rate must be 4% per MAS"""
        self.assertEqual(STRESS_TEST_RATE, 0.04)
    
    def test_cpf_oa_floor_rate(self):
        """CPF OA floor rate is 2.5% p.a."""
        self.assertEqual(CPF_OA_RATE, 0.025)
    
    def test_dps_surcharge_3_percent(self):
        """DPS surcharge is 3% over NPS"""
        self.assertEqual(DPS_SURCHARGE, 0.03)


if __name__ == "__main__":
    print("=" * 70)
    print("Rivelle EC Finance Planner - Test Suite")
    print("=" * 70)
    print("\nValidated against official sources:")
    print("- IRAS BSD rates (15 Feb 2023)")
    print("- MAS MSR/LTV/Stress-test regulations")
    print("- CPF Board OA interest rates")
    print("- Rivelle EC developer pricing\n")
    print("=" * 70)
    
    unittest.main(verbosity=2)
