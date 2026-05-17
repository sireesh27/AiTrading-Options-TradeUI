"""
Quick script to check what balance fields are available from each broker.
"""
import main_tastytrade as tasty_bot
import alpaca_trader
from tastytrade import Account

print("=" * 80)
print("CHECKING AVAILABLE BALANCE FIELDS")
print("=" * 80)

# TastyTrade
print("\n1. TASTYTRADE BALANCES:")
print("-" * 80)
try:
    session = tasty_bot.authenticate()
    if session:
        account = Account.get(session)[0]
        balances = account.get_balances(session)

        # Print all non-private attributes
        balance_fields = [attr for attr in dir(balances) if not attr.startswith('_')]
        print(f"Available fields ({len(balance_fields)}):")
        for field in balance_fields:
            try:
                value = getattr(balances, field)
                if not callable(value):
                    print(f"  {field}: {value}")
            except:
                pass
except Exception as e:
    print(f"Error: {e}")

# Alpaca
print("\n2. ALPACA ACCOUNT INFO:")
print("-" * 80)
try:
    client = alpaca_trader.authenticate_paper()
    if client:
        account = client.get_account()

        # Print all attributes
        account_fields = [attr for attr in dir(account) if not attr.startswith('_')]
        print(f"Available fields ({len(account_fields)}):")
        for field in account_fields:
            try:
                value = getattr(account, field)
                if not callable(value):
                    print(f"  {field}: {value}")
            except:
                pass
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)
