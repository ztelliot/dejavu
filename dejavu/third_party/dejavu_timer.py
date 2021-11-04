import codetiming


class DejavuTimer(codetiming.Timer):
    # works on the level of context manager, can be turned on and off dynamically
    timing_enabled = False
    # disables generation of decorators, hardcoded parameter
    _decorators_disabled = False

    def __init__(self, name, logger=print):
        super().__init__(name=name, logger=logger, text="{name}:\t{:0.4f} seconds\t({milliseconds} ms)")

    def __call__(self, func):
        if DejavuTimer._decorators_disabled:
            return func
        else:
            return super().__call__(func)

    def __enter__(self):
        if DejavuTimer.timing_enabled:
            return super().__enter__()
        else:
            return None

    def __exit__(self, *args):
        if DejavuTimer.timing_enabled:
            super().__exit__(*args)
        else:
            pass
