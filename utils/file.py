import os
import time

class File:
    @staticmethod
    def is_older_than(filepath, max_age_days=1):
        if not os.path.exists(filepath):
            return True
        last_modified = os.path.getmtime(filepath)
        age_days = (time.time() - last_modified) / (60 * 60 * 24)
        return age_days > max_age_days