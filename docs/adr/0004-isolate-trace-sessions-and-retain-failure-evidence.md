# Isolate trace sessions and retain failure evidence

Development captures will use a session identity and separate artifact directory. A session keeps
recent debug images bounded, then copies evidence referenced by a terminal failure into its failure
bundle. This keeps everyday runs small while making a failure report self-contained and preventing
append-only logs from mixing unrelated executions.
