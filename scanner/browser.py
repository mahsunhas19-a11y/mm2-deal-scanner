import os


def launch_chromium(playwright):
    """Launch Chromium visibly on a PC and headlessly in cloud runners."""
    headless = os.environ.get("MM2_HEADLESS", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }
    args = ["--disable-dev-shm-usage"] if headless else []
    return playwright.chromium.launch(headless=headless, args=args)
