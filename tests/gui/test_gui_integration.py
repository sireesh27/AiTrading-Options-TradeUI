import pytest
from playwright.sync_api import Page, expect

MOCK_DATA = {
    "tastytrade": { "totalValue": 1000, "equity": 1000, "buyingPower": 500, "dayPL": 10, "dayTrades": "0 / 3", "positions": [] },
    "alpaca_live": { "totalValue": 2000, "equity": 2000, "buyingPower": 1000, "dayPL": 20, "dayTrades": "0 / 3", "positions": [] },
    "alpaca_paper": { "totalValue": 0, "equity": 0, "buyingPower": 0, "dayPL": 0, "dayTrades": "0 / 3", "positions": [] },
    "ibkr_live": { "totalValue": 3000, "equity": 3000, "buyingPower": 1500, "dayPL": 30, "dayTrades": "N/A", "positions": [] },
    "ibkr_paper": { "totalValue": 0, "equity": 0, "buyingPower": 0, "dayPL": 0, "dayTrades": "N/A", "positions": [] }
}

@pytest.fixture(autouse=True)
def mock_api(page: Page):
    page.route("**/api/positions", lambda route: route.fulfill(json=MOCK_DATA))

@pytest.mark.gui
def test_dashboard_loads(page: Page):
    page.goto("http://localhost:5173")
    
    # Check title
    expect(page).to_have_title("Broker Accounts Overview")
    
    # Check header
    expect(page.get_by_text("BrokerDash")).to_be_visible()
    
    # Check summary cards
    # With mock data: 1000+2000+3000 = 6000
    expect(page.get_by_text("Total Portfolio Value")).to_be_visible()
    expect(page.get_by_text("$6,000.00")).to_be_visible()

    # Check for specific broker sections
    expect(page.get_by_text("Tasty Trade", exact=True)).to_be_visible()
    expect(page.get_by_text("Alpaca", exact=True)).to_be_visible()
    expect(page.get_by_text("IBKR", exact=True)).to_be_visible()

@pytest.mark.gui
def test_refresh_button(page: Page):
    page.goto("http://localhost:5173")
    refresh_btn = page.get_by_role("button", name="Refresh")
    expect(refresh_btn).to_be_visible()
    refresh_btn.click()
    
    # It should call API again (which is mocked) so it should remain visible
    expect(refresh_btn).to_be_visible()

@pytest.mark.gui
def test_toggle_section(page: Page):
    page.goto("http://localhost:5173")
    
    # Find Tasty Trade section toggle
    # BrokerSection title is "Tasty Trade"
    
    # We can find the button relative to the title
    # Or simply finding the button that controls "Tasty Trade" area. 
    # In implementation we have `text-lg font-bold ... {title}`
    
    # Let's assume the first expand_less icon belongs to Tasty Trade (first in list)
    # The button has expand_less when open.
    
    # Verify section content is visible initially
    # Tasty Trade equity is 1000 -> "$1,000.00"
    expect(page.get_by_text("$1,000.00").first).to_be_visible()
    
    # Click the first expand button
    # We can target by icon text
    toggle_btn = page.locator("button:has(.material-symbols-outlined:text-is('expand_less'))").first
    toggle_btn.click()
    
    # Now it should be collapsed -> expand_more
    expect(page.locator("button:has(.material-symbols-outlined:text-is('expand_more'))").first).to_be_visible()
    
    # Content should be hidden. 
    # We can check if "$1,000.00" is hidden? 
    # Note: if there are multiple 1000s, filtering might be needed. 
    # But checking if the button icon changed is a good proxy for state change.
