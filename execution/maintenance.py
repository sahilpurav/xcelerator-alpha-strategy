import os
import shutil


def run_clean():
    """
    Delete all cached files and reset the strategy state.
    This will remove all cached price data and reset the strategy state.
    """
    if os.path.exists("cache"):
        shutil.rmtree("cache")
        print("🗑️ Removed 'cache' folder.")
    if os.path.exists("output"):
        shutil.rmtree("output")
        print("🗑️ Removed 'output' folder.")
    else:
        print("✅ Nothing to delete.")
