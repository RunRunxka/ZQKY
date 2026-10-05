# Pure material regression first round preserved

`material-regression-v1/COMMAND.json` records PID 15676, exit 1, elapsed 10540.381 ms, source zero drift, captured OS birth, actual process wait and closed logs. The runner incorrectly shared one exclusive `AUTHOR_RUN_DIR` across two legacy test classes, yielding 49 setup errors. The new nested TEMP environment also changed the expected readonly source-root refusal from `seed.catalogPaths` to `dataRoot`, yielding one failure / 51 passed. The original assertions/tool source were not changed. New independent rounds give each group its own output and restore the standard OS TEMP root only for these pure-material, app/env/SQL/network-forbidden CLIs. This does not access a source database; production trial isolation remains new TEMP.

