# G6-V00 preparation STOP v1

Preparation is complete and all V00 preparation writes are STOPPED pending ROOT binding and explicit release. Components/browser/full E2E have not run. Static TypeScript parsing only passed with zero parse diagnostics, PID22552, elapsed65.4916ms, exit0; complete command/SHA/identity facts are in PREPARATION-STATIC-v1.json. It imports no test module, component, app.main or browser and changes no service.

Planned independent component gate: exactly16 files/211 cases =152 old G5 independent +26 old G5 continuous +5 old operation +8 old review cache-owner +20 new handwritten. G6 author83 is outside this independent count. New browser complete gate: exactly16 cases =8 new G6 same-fresh-Context/two-ready-Page real localStorage cases +8 byte-identical old G5 regression. Existing full gate remains29spec/174 with original21UI/R14, zero retries/skips. No executed pass is claimed by preparation.

| Frozen preparation input | SHA256 |
| --- | --- |
| vitest.config.ts | 511768ab28422a8dfca0b26cb6034d46a45cd8ec8d96f888abb9a1066014935f |
| owned-ack.test.tsx | 00580acffb078e8bcbc00110bfe8a617b37241266d71ab20edc4ab81892fdefd |
| browser/external.config.ts | 7c62ea870082e7327459dda84d18176dd7d0296945432c4bf597b8f6f8c7f778 |
| browser/g6.spec.ts | 0d2aedcf9ef6a5fc86725908725c53efaba277687fa4f50122e6b1832a0da9e5 |
| browser/g5-regression.spec.ts | a797d216a4defb73ac4b7c90e6f7e5bc90be06067ff0b91e299de9051bc5acbe |
| PLAN-v1.md | 37183ecf9380fee97c21e8fe51f680990777ef7cfaa632941b6f4c134ed63b1d |
| ORACLE-v1.json | b7195f50dccfd204ea20cf3c4036b1e5bc4daa1d30fd878be5de2a4f8f051bd3 |

The old browser SHA is also a797d216a4defb73ac4b7c90e6f7e5bc90be06067ff0b91e299de9051bc5acbe; its original assertions and relative import depth are unchanged. New configs require G6_COMPONENT_RUN or G6_RUN/G6_SUITE, use only new cache/output labels, retries0 and browser trace:on/webServer undefined. ROOT checks output path absence and owns build/service/runner. This STOP is preparation status, not independent G6 acceptance. Actual current check is a ROOT gate; V00 has not yet read or signed its logs. B7B source/author QA remains outside the G6 lane and will need its own freeze/acceptance.
