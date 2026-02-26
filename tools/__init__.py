from tools import portfolio_summary, market_data, transaction_history, risk_assessment, tax_estimate

ALL_TOOLS = {
    "portfolio_summary": portfolio_summary,
    "market_data": market_data,
    "transaction_history": transaction_history,
    "risk_assessment": risk_assessment,
    "tax_estimate": tax_estimate,
}

TOOL_DEFINITIONS = [mod.TOOL_DEFINITION for mod in ALL_TOOLS.values()]
