from tools import (
    portfolio_summary,
    market_data,
    stock_history,
    transaction_history,
    risk_assessment,
    tax_estimate,
    performance,
    dividend_history,
    portfolio_report,
    investment_timeline,
    account_overview,
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
}

TOOL_DEFINITIONS = [mod.TOOL_DEFINITION for mod in ALL_TOOLS.values()]
