"""Shim for the two prototype test files (test_burst.py, test_group_asym.py). The prototype module group_asym.py was
folded into alpha_options_lab.py with a ga_ prefix; this maps the old names onto the lab's."""
import alpha_options_lab as _L


def __getattr__(name):
    for cand in (name, f"ga_{name}", f"_ga_{name}"):
        if hasattr(_L, cand):
            return getattr(_L, cand)
    raise AttributeError(f"alpha_options_lab has no {name} or ga_{name}")
