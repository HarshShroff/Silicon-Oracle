
import streamlit as st
from utils.alpaca import get_alpaca_trader

st.secrets = {
    "alpaca": {
        # Placeholder, relies on actual secrets being present in environment or handled by the utils
        "api_key": "PKM5K8P8K8K8K8K8K8K8",
        "secret_key": "..."
    }
}
# Actually the code reads from st.secrets. We cannot easily inject secrets here if running as standalone script unless we use streamlit run.
# I will use the app's context.

trader = get_alpaca_trader()

if trader.is_connected():
    orders = trader.get_orders(status="closed")
    print(f"Found {len(orders)} closed orders.")
    for o in orders:
        print(
            f"ID: {o['order_id']}, Ticker: {o['ticker']}, Status: {o['status']}, Price: {o.get('filled_avg_price')}")
else:
    print("Not connected.")
