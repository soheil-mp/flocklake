"""Test configuration shared by every package in the workspace.

Hypothesis profiles:

- ``dev`` (default): quick, randomised runs while developing.
- ``ci``: more examples, derandomised so a CI failure always reproduces, no deadline
  because shared runners have noisy timing.

Select one with the ``HYPOTHESIS_PROFILE`` environment variable.
"""

import os

from hypothesis import settings

settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=500, derandomize=True, deadline=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
