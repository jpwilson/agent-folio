from tools import (
    account_overview,
    dividend_history,
    invest_insight_demographics,
    invest_insight_properties,
    invest_insight_search,
    investment_timeline,
    market_data,
    performance,
    portfolio_report,
    portfolio_summary,
    risk_assessment,
    stock_history,
    tax_estimate,
    transaction_history,
)

ALL_TOOLS = {
    "portfolio_summary": portfolio_summary,
    "market_data": market_data,
    "stock_history": stock_history,
    "transaction_history": transaction_history,
    "risk_assessment": risk_assessment,
    "tax_estimate": tax_estimate,
    "portfolio_performance": performance,
    "dividend_history": dividend_history,
    "portfolio_report": portfolio_report,
    "investment_timeline": investment_timeline,
    "account_overview": account_overview,
    "invest_insight_search": invest_insight_search,
    "invest_insight_properties": invest_insight_properties,
    "invest_insight_demographics": invest_insight_demographics,
}

TOOL_DEFINITIONS = [mod.TOOL_DEFINITION for mod in ALL_TOOLS.values()]
