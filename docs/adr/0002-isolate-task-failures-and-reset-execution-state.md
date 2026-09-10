# Isolate task failures and reset execution state

MaaPlus will treat timeout, handler exception, and exhausted retry attempts as outcomes of one task
execution. The scheduler will continue independent work, while each periodic trigger receives a
fresh execution context so state from a prior run cannot silently leak into the next one. Recovery
remains bounded and observable through the development trace.
