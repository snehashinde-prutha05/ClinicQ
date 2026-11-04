import os
import urllib.error

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from helpers import URL, post


@pytest.fixture(scope="session")
def driver():
    opts = Options()
    if os.environ.get("HEADLESS") == "1":
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    # stop Chrome's password manager / leak-warning pop-ups from interfering with the login tests
    opts.add_experimental_option("prefs", {"credentials_enable_service": False,
                                           "profile.password_manager_enabled": False,
                                           "profile.password_manager_leak_detection": False})
    opts.add_argument("--disable-save-password-bubble")
    d = webdriver.Chrome(options=opts)   # Selenium 4 downloads the matching driver itself
    yield d
    d.quit()


@pytest.fixture(autouse=True)
def clean_state(driver):
    """Every test starts with an empty queue and no login."""
    try:
        post("/__test__/reset")
    except urllib.error.HTTPError:
        pytest.exit("The app is not in test mode. Start it with CLINICQ_TEST=1 (see README).", 1)
    except urllib.error.URLError:
        pytest.exit(f"Cannot reach the app at {URL}. Start it first with: python app.py", 1)
    driver.get(URL + "/")
    driver.delete_all_cookies()