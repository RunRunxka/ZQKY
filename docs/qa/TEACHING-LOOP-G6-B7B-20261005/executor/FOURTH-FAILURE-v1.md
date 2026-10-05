# Fourth complete round preserved

`self-check-fourth/COMMAND.json` records PID 16796, exit 1, elapsed 14742.818 ms, zero candidate SHA drift. Full logs retain 49 passed / 1 failed. The cancellation test did not assert the actual production JobEngine's propagated `asyncio.CancelledError`; it expected normal return after shutdown. The corrected oracle explicitly accepts cancellation propagation and independently asserts one send, unknown state, full reservation and STOP. No production behavior or budget rule is relaxed.

