import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import calendar

st.set_page_config(page_title="Rivelle EC Finance Planner", layout="wide")

DPS_SURCHARGE = 0.03

UNIT_TYPES = {
    "3BR Premium": {"nps_price": 1_588_000, "sqft": 883, "psf": 1798},
    "3BR Premium + Study": {"nps_price": 1_663_000, "sqft": 926, "psf": 1796},
    "4 Bedroom": {"nps_price": 1_893_000, "sqft": 1044, "psf": 1813},
}
for _ut in UNIT_TYPES.values():
    _ut["dps_price"] = round(_ut["nps_price"] * (1 + DPS_SURCHARGE))

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
STRESS_TEST_RATE = 0.04


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
    max_monthly = monthly_income * 0.30
    r = stress_rate / 12
    n = tenure_years * 12
    if r == 0:
        return max_monthly * n
    return max_monthly * ((1 + r) ** n - 1) / (r * (1 + r) ** n)


def compute_dps_milestones(price, bsd, starting_cash, starting_cpf, liquidity_floor, priority):
    milestones = []
    cash = starting_cash
    cpf = starting_cpf

    events = [
        ("Booking Fee (5%)", BOOKING_DATE, price * 0.05, "cash_only"),
        ("OTP Exercise (15%)", OTP_DATE, price * 0.15, "cash_or_cpf"),
        ("Buyer's Stamp Duty", OTP_DATE + timedelta(days=14), bsd, "cash_only"),
    ]

    for name, date, amount, source_rule in events:
        from_cash = 0.0
        from_cpf = 0.0
        status = "OK"

        if source_rule == "cash_only":
            from_cash = amount
            from_cpf = 0.0
        elif priority == "Cash First":
            available_cash = max(0, cash - liquidity_floor)
            from_cash = min(amount, available_cash)
            from_cpf = amount - from_cash
        else:
            from_cpf = min(amount, cpf)
            from_cash = amount - from_cpf

        if from_cpf > cpf:
            shortfall = from_cpf - cpf
            from_cpf = cpf
            from_cash += shortfall

        if cash - from_cash < liquidity_floor:
            if cash - from_cash < 0:
                status = "BREACH"
            else:
                status = "WARNING"

        if from_cash + from_cpf < amount:
            status = "BREACH"

        cash -= from_cash
        cpf -= from_cpf

        milestones.append({
            "Milestone": name,
            "Date": date.strftime("%b %Y"),
            "Amount Due": amount,
            "From Cash": from_cash,
            "From CPF": from_cpf,
            "Cash After": cash,
            "CPF After": cpf,
            "Status": status,
        })

    return milestones, cash, cpf


def simulate_accumulation(start_cash, start_cpf, monthly_savings, monthly_cpf,
                          cpf_annual_rate, milestones_list, total_months=50):
    quarterly_rate = cpf_annual_rate / 4

    milestone_map = {}
    for m in milestones_list:
        dt = datetime.strptime(m["Date"], "%b %Y")
        key = (dt.year, dt.month)
        if key not in milestone_map:
            milestone_map[key] = {"cash_out": 0, "cpf_out": 0, "event": m["Milestone"]}
        milestone_map[key]["cash_out"] += m["From Cash"]
        milestone_map[key]["cpf_out"] += m["From CPF"]
        existing_event = milestone_map[key]["event"]
        if m["Milestone"] not in existing_event:
            milestone_map[key]["event"] = existing_event + " + " + m["Milestone"]

    records = []
    cash = start_cash
    cpf = start_cpf
    current = BOOKING_DATE

    for i in range(total_months + 1):
        dt = add_months(current, i)
        key = (dt.year, dt.month)
        event = ""

        if i > 0:
            cash += monthly_savings
            cpf += monthly_cpf

        if key in milestone_map:
            cash -= milestone_map[key]["cash_out"]
            cpf -= milestone_map[key]["cpf_out"]
            event = milestone_map[key]["event"]

        if dt.month in (3, 6, 9, 12) and i > 0:
            cpf *= (1 + quarterly_rate)

        records.append({
            "Month": i,
            "Date": dt.strftime("%b %Y"),
            "date_obj": dt,
            "Cash Balance": cash,
            "CPF OA Balance": cpf,
            "Event": event,
        })

    return pd.DataFrame(records)


def run_full_simulation(price, income, monthly_savings, monthly_cpf, starting_cash,
                        starting_cpf, loan_rate, tenure, liquidity_floor, cpf_rate, priority):
    bsd = calculate_bsd(price)
    max_loan_msr = calculate_max_loan(income, STRESS_TEST_RATE, tenure)
    max_loan_ltv = price * 0.75
    max_loan = min(max_loan_msr, max_loan_ltv)
    msr_cap = income * 0.30

    milestones, post_ms_cash, post_ms_cpf = compute_dps_milestones(
        price, bsd, starting_cash, starting_cpf, liquidity_floor, priority
    )

    top_months = (TOP_DATE.year - BOOKING_DATE.year) * 12 + (TOP_DATE.month - BOOKING_DATE.month)
    csc_months = (CSC_DATE.year - BOOKING_DATE.year) * 12 + (CSC_DATE.month - BOOKING_DATE.month)

    df = simulate_accumulation(
        starting_cash, starting_cpf, monthly_savings, monthly_cpf,
        cpf_rate, milestones, total_months=csc_months
    )

    top_row = df[df["Month"] == top_months].iloc[0]
    cash_at_top = top_row["Cash Balance"]
    cpf_at_top = top_row["CPF OA Balance"]

    amount_due_top = price * 0.65
    amount_due_csc = price * 0.15
    loan_amount = min(max_loan, amount_due_top)
    top_shortfall = amount_due_top - loan_amount
    cpf_for_top = min(cpf_at_top, top_shortfall)
    cash_for_top = min(max(0, cash_at_top - liquidity_floor), top_shortfall - cpf_for_top)
    top_funding = loan_amount + cpf_for_top + cash_for_top
    top_surplus = top_funding - amount_due_top

    cash_after_top = cash_at_top - cash_for_top
    cpf_after_top = cpf_at_top - cpf_for_top

    months_to_csc = csc_months - top_months
    cash_at_csc = cash_after_top + (monthly_savings * months_to_csc)
    cpf_at_csc = cpf_after_top + (monthly_cpf * months_to_csc)
    quarters_to_csc = months_to_csc // 3
    for _ in range(quarters_to_csc):
        cpf_at_csc *= (1 + cpf_rate / 4)

    cpf_for_csc = min(cpf_at_csc, amount_due_csc)
    cash_for_csc = min(max(0, cash_at_csc - liquidity_floor), amount_due_csc - cpf_for_csc)
    csc_funding = cpf_for_csc + cash_for_csc
    csc_surplus = csc_funding - amount_due_csc

    monthly_repayment = calculate_monthly_repayment(loan_amount, loan_rate, tenure)
    total_repaid = monthly_repayment * tenure * 12
    total_interest = total_repaid - loan_amount
    msr_util = (monthly_repayment / msr_cap * 100) if msr_cap > 0 else 0

    min_cash = df["Cash Balance"].min()
    floor_breached = min_cash < liquidity_floor
    close_to_floor = min_cash < (liquidity_floor + 20_000)
    has_top_shortfall = top_surplus < 0
    tight_top = 0 <= top_surplus < 50_000
    has_csc_shortfall = csc_surplus < 0

    if floor_breached or has_top_shortfall or has_csc_shortfall:
        verdict = "NOT VIABLE"
    elif close_to_floor or tight_top:
        verdict = "AT RISK"
    else:
        verdict = "VIABLE"

    risks = []
    if floor_breached:
        risks.append(f"Cash drops to ${min_cash:,.0f}, below ${liquidity_floor:,.0f} minimum")
    if close_to_floor and not floor_breached:
        risks.append(f"Cash dips to ${min_cash:,.0f}, close to ${liquidity_floor:,.0f} minimum")
    if has_top_shortfall:
        risks.append(f"TOP settlement shortfall of ${abs(top_surplus):,.0f}")
    if tight_top and not has_top_shortfall:
        risks.append(f"Tight TOP surplus of only ${top_surplus:,.0f}")
    if has_csc_shortfall:
        risks.append(f"CSC settlement shortfall of ${abs(csc_surplus):,.0f}")

    total_pre_top = sum(m["Amount Due"] for m in milestones)

    return {
        "price": price,
        "bsd": bsd,
        "max_loan": max_loan,
        "max_loan_msr": max_loan_msr,
        "max_loan_ltv": max_loan_ltv,
        "msr_cap": msr_cap,
        "milestones": milestones,
        "df": df,
        "amount_due_top": amount_due_top,
        "amount_due_csc": amount_due_csc,
        "loan_amount": loan_amount,
        "cpf_at_top": cpf_at_top,
        "cash_at_top": cash_at_top,
        "cpf_for_top": cpf_for_top,
        "cash_for_top": cash_for_top,
        "top_funding": top_funding,
        "top_surplus": top_surplus,
        "cash_at_csc": cash_at_csc,
        "cpf_at_csc": cpf_at_csc,
        "cpf_for_csc": cpf_for_csc,
        "cash_for_csc": cash_for_csc,
        "csc_funding": csc_funding,
        "csc_surplus": csc_surplus,
        "monthly_repayment": monthly_repayment,
        "total_interest": total_interest,
        "total_repaid": total_repaid,
        "msr_util": msr_util,
        "verdict": verdict,
        "risks": risks,
        "total_pre_top": total_pre_top,
        "min_cash": min_cash,
    }


st.title("Rivelle EC Finance Planner")
st.caption("James & Tiffani | Rivelle Tampines EC | Deferred Payment Scheme (5/15/65/15)")

if "prev_unit_type" not in st.session_state:
    st.session_state.prev_unit_type = "3BR Premium + Study"
if "purchase_price" not in st.session_state:
    st.session_state.purchase_price = UNIT_TYPES["3BR Premium + Study"]["dps_price"]

with st.sidebar:
    st.header("Configuration")

    st.subheader("Property")
    unit_type = st.radio("Unit Type", list(UNIT_TYPES.keys()), index=1)
    if unit_type != st.session_state.prev_unit_type:
        st.session_state.purchase_price = UNIT_TYPES[unit_type]["dps_price"]
        st.session_state.prev_unit_type = unit_type
    nps_base = UNIT_TYPES[unit_type]["nps_price"]
    st.caption(f"NPS Base: ${nps_base:,} | DPS Surcharge: +{DPS_SURCHARGE*100:.0f}%")
    purchase_price = st.number_input("DPS Purchase Price ($)",
                                     step=1000, min_value=500_000, key="purchase_price")

    st.subheader("Income & Savings")
    james_income = st.number_input("James Monthly Income ($)", value=10_653.04, step=100.0, min_value=0.0)
    tiffani_income = st.number_input("Tiffani Monthly Income ($)", value=6_000.00, step=100.0, min_value=0.0)
    combined_income = james_income + tiffani_income
    st.caption(f"Combined: ${combined_income:,.2f}/mo")
    monthly_savings = st.slider("Monthly Cash Savings ($)", 2_000, 15_000, 8_000, step=500)
    monthly_cpf = st.slider("Monthly CPF OA Contribution ($)", 2_000, 8_000, 4_000, step=500)

    st.subheader("Starting Balances")
    starting_cash = st.number_input("Liquid Cash ($)", value=280_000, step=10_000)
    starting_cpf_oa = st.number_input("CPF OA Balance ($)", value=200_000, step=10_000)

    st.subheader("Loan Parameters")
    st.caption("MAS stress-test rate: 4.0% (used for MSR loan cap)")
    loan_rate = st.slider("Actual Bank Loan Rate (%)", 2.5, 5.5, 4.0, step=0.1) / 100
    loan_tenure = st.slider("Loan Tenure (years)", 20, 30, 30)

    st.subheader("Constraints")
    liquidity_floor = st.number_input("Minimum Total Savings ($)", value=40_000, step=5_000, min_value=0)
    cpf_rate = 0.025
    payment_priority = "CPF First"

result = run_full_simulation(
    purchase_price, combined_income, monthly_savings, monthly_cpf,
    starting_cash, starting_cpf_oa, loan_rate, loan_tenure,
    liquidity_floor, cpf_rate, payment_priority,
)

with st.expander("Financial Assumptions", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**BUYERS**")
        st.text("James (SC) + Tiffani (SC)")
        st.text("Income Ceiling Waiver: Approved")
        st.markdown("---")
        st.markdown("**INCOME & SAVINGS**")
        st.text(f"James Monthly Income:     ${james_income:>12,.2f} *")
        st.text(f"Tiffani Monthly Income:   ${tiffani_income:>12,.2f} *")
        st.text(f"Combined Monthly Income:  ${combined_income:>12,.2f} (derived)")
        st.text(f"Monthly Cash Savings:     ${monthly_savings:>12,} *")
        st.text(f"Monthly CPF OA Contrib:   ${monthly_cpf:>12,} *")
        st.markdown("---")
        st.markdown("**PROPERTY**")
        st.text(f"Unit Type:      {unit_type}")
        st.text(f"NPS Base Price: ${UNIT_TYPES[unit_type]['nps_price']:>12,} (reference)")
        st.text(f"DPS Surcharge:  {DPS_SURCHARGE*100:>11.0f}% (developer)")
        st.text(f"DPS Price:      ${purchase_price:>12,} *")
        st.text(f"BSD:            ${result['bsd']:>12,.0f} (derived, on DPS price)")
    with c2:
        st.markdown("**STARTING BALANCES**")
        st.text(f"Liquid Cash:    ${starting_cash:>12,} *")
        st.text(f"CPF OA:         ${starting_cpf_oa:>12,} *")
        st.text(f"S&P 500 ETFs:   ${570_000:>12,} (not used)")
        st.markdown("---")
        st.markdown("**LOAN PARAMETERS**")
        st.text(f"MAS Stress-Test Rate: {STRESS_TEST_RATE*100:>6.1f}% (regulatory)")
        st.text(f"Actual Bank Rate:     {loan_rate*100:>6.1f}% *")
        st.text(f"Max Loan (MSR):  ${result['max_loan']:>11,.0f} (derived)")
        st.text(f"Tenure:          {loan_tenure:>9} years *")
        st.text(f"LTV Cap:         {75:>9}% (regulatory)")
        st.markdown("---")
        st.markdown("**CONSTRAINTS**")
        st.text(f"MSR Cap:          ${result['msr_cap']:>10,.2f}/mo (derived)")
        st.text(f"Min Total Savings:${liquidity_floor:>10,} *")
        st.text(f"CPF OA Rate:      {cpf_rate*100:>9.1f}% p.a. (fixed)")
        st.text(f"Payment Priority: {payment_priority:>10} (fixed)")
    st.caption("* = editable in sidebar | (derived) = auto-calculated | (regulatory) = fixed rule")
    st.markdown("**DPS TIMELINE**: Booking 5% -> Apr 2026 | OTP 15% -> Jun 2026 | 65% -> Jun 2030 (TOP) | 15% -> Jun 2033 (CSC)")

st.markdown("---")
st.subheader("Executive Summary")

ec1, ec2, ec3, ec4, ec5 = st.columns(5)
ec1.metric("Purchase Price", f"${purchase_price:,.0f}")
ec2.metric("Pre-TOP Outlay", f"${result['total_pre_top']:,.0f}")
top_outlay = result['total_pre_top'] + (result['amount_due_top'] - result['loan_amount'])
ec3.metric("Total Outlay at TOP", f"${top_outlay:,.0f}")
ec4.metric("CSC Balance (15%)", f"${result['amount_due_csc']:,.0f}")
ec5.metric("Monthly Repayment", f"${result['monthly_repayment']:,.2f}")

st.markdown("---")
st.subheader("DPS Payment Timeline")
ms_df = pd.DataFrame(result["milestones"])

def style_milestone_row(row):
    if row["Status"] == "BREACH":
        return ["background-color: #ffcccc; color: #721c24"] * len(row)
    elif row["Status"] == "WARNING":
        return ["background-color: #fff3cd; color: #856404"] * len(row)
    return [""] * len(row)

display_df = ms_df.copy()
for col in ["Amount Due", "From Cash", "From CPF", "Cash After", "CPF After"]:
    display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")

st.dataframe(
    display_df.style.apply(style_milestone_row, axis=1),
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")
st.subheader("Cash Flow Projection (Apr 2026 - Jun 2033)")

sim_df = result["df"]
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=sim_df["Date"], y=sim_df["Cash Balance"],
    name="Cash Balance", line=dict(color="#1f77b4", width=2),
))
fig.add_trace(go.Scatter(
    x=sim_df["Date"], y=sim_df["CPF OA Balance"],
    name="CPF OA Balance", line=dict(color="#2ca02c", width=2),
))
fig.add_hline(
    y=liquidity_floor, line_dash="dash", line_color="red",
    annotation_text=f"Min Total Savings (${liquidity_floor:,})",
    annotation_position="top left",
)

for _, row in sim_df[sim_df["Event"] != ""].iterrows():
    fig.add_vline(x=row["Date"], line_dash="dot", line_color="gray", opacity=0.5)
    fig.add_annotation(x=row["Date"], y=max(row["Cash Balance"], row["CPF OA Balance"]),
                       text=row["Event"], showarrow=True, arrowhead=2, font=dict(size=9))

fig.update_layout(
    yaxis_title="Balance ($)", xaxis_title="Month",
    height=450, margin=dict(t=30, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("TOP Settlement Breakdown (June 2030) — 65%")
top_data = {
    "Item": [
        "65% Balance Due at TOP",
        "Bank Loan",
        "CPF OA Used at TOP",
        "Cash Used at TOP",
        "Total Funding",
        "Surplus / (Shortfall)",
    ],
    "Amount": [
        f"${result['amount_due_top']:,.0f}",
        f"${result['loan_amount']:,.0f}",
        f"${result['cpf_for_top']:,.0f}",
        f"${result['cash_for_top']:,.0f}",
        f"${result['top_funding']:,.0f}",
        f"${result['top_surplus']:,.0f}",
    ],
}
st.table(pd.DataFrame(top_data))

st.markdown("---")
st.subheader("CSC Settlement Breakdown (June 2033) — 15%")
csc_data = {
    "Item": [
        "15% Balance Due at CSC",
        "CPF OA Available at CSC",
        "Cash Available at CSC (net of floor)",
        "CPF Used for CSC",
        "Cash Used for CSC",
        "Total Funding",
        "Surplus / (Shortfall)",
    ],
    "Amount": [
        f"${result['amount_due_csc']:,.0f}",
        f"${result['cpf_at_csc']:,.0f}",
        f"${max(0, result['cash_at_csc'] - liquidity_floor):,.0f}",
        f"${result['cpf_for_csc']:,.0f}",
        f"${result['cash_for_csc']:,.0f}",
        f"${result['csc_funding']:,.0f}",
        f"${result['csc_surplus']:,.0f}",
    ],
}
st.table(pd.DataFrame(csc_data))

st.markdown("---")
st.subheader("Loan Repayment")
lc1, lc2, lc3, lc4 = st.columns(4)
lc1.metric("Monthly Repayment", f"${result['monthly_repayment']:,.2f}")
lc2.metric("Total Interest", f"${result['total_interest']:,.0f}")
lc3.metric("MSR Utilization", f"{result['msr_util']:.1f}%")
lc4.metric("Total Repaid", f"${result['total_repaid']:,.0f}")

st.markdown("---")
st.subheader("Viability Verdict")
if result["verdict"] == "VIABLE":
    st.success(f"**VIABLE** - {unit_type} at ${purchase_price:,} is financially feasible.")
elif result["verdict"] == "AT RISK":
    st.warning(f"**AT RISK** - {unit_type} at ${purchase_price:,} is feasible but tight.")
else:
    st.error(f"**NOT VIABLE** - {unit_type} at ${purchase_price:,} has critical issues.")

if result["risks"]:
    for risk in result["risks"]:
        st.markdown(f"- {risk}")

st.markdown("---")
st.subheader("Side-by-Side Comparison")
comparison_rows = []
for utype, udata in UNIT_TYPES.items():
    dps_p = udata["dps_price"]
    r = run_full_simulation(
        dps_p, combined_income, monthly_savings, monthly_cpf,
        starting_cash, starting_cpf_oa, loan_rate, loan_tenure,
        liquidity_floor, cpf_rate, payment_priority,
    )
    comparison_rows.append({
        "Unit Type": utype,
        "DPS Price": f"${dps_p:,}",
        "BSD": f"${r['bsd']:,.0f}",
        "NPS Price": f"${udata['nps_price']:,}",
        "Booking (5%)": f"${udata['dps_price'] * 0.05:,.0f}",
        "OTP (15%)": f"${udata['dps_price'] * 0.15:,.0f}",
        "Pre-TOP Outlay": f"${r['total_pre_top']:,.0f}",
        "65% at TOP": f"${r['amount_due_top']:,.0f}",
        "15% at CSC": f"${r['amount_due_csc']:,.0f}",
        "Loan": f"${r['loan_amount']:,.0f}",
        "TOP Surplus": f"${r['top_surplus']:,.0f}",
        "CSC Surplus": f"${r['csc_surplus']:,.0f}",
        "Monthly Repay": f"${r['monthly_repayment']:,.2f}",
        "MSR %": f"{r['msr_util']:.1f}%",
        "Verdict": r["verdict"],
    })

comp_df = pd.DataFrame(comparison_rows)

def style_verdict(val):
    if val == "VIABLE":
        return "background-color: #d4edda; color: #155724"
    elif val == "AT RISK":
        return "background-color: #fff3cd; color: #856404"
    else:
        return "background-color: #f8d7da; color: #721c24"

styled = comp_df.style.map(style_verdict, subset=["Verdict"])
st.dataframe(styled, use_container_width=True, hide_index=True)
