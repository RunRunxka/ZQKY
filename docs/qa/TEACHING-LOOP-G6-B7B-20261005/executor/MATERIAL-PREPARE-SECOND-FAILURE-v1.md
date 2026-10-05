# Prepare material regression second round preserved

`material-prepare-v2/COMMAND.json` records PID 13400, exit 1, elapsed 30392.924 ms, X candidate zero drift, actual OS birth/wait. 48 tests and 34 subtests passed; the only failing test's expected CLI refusal was correct, but its required all-tool snapshot detected sibling R's `trial_result_check.py` changing from `9f70da7dad8ff3a470bfdde8eeea8ebacedff5da3b2c374e96c89060562ffd33` to `bb49e5ba8461d33226a1367e212ab3c2c9c95106f935c0b9378bdda7043434ab` during execution. R then froze its allowed product files. A separate complete v3 round checks the stable package; no failed-round result is spliced or deleted.

