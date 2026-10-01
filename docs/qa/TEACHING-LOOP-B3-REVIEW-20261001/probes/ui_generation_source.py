"""Produce actual HTTP generation receipt and terminal view using a controlled provider."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="b3-review-ui-generate-") as directory:
        root = Path(directory)
        os.environ["ZQKY_DATA_DIR"] = str(root / "default-isolated")
        from tests.test_question_generation import GenerationHarness, generation_reply
        harness = GenerationHarness(root / "scene")
        try:
            harness.provider.replies = [generation_reply()]
            receipt = harness.start_generation()
            assert receipt.status_code == 202, receipt.text
            accepted = receipt.json()
            terminal = harness.wait_job(accepted["jobId"])
            assert accepted["attempt"] == 0, accepted
            assert terminal["attempt"] == 1 and terminal["state"] == "succeeded", terminal
            destination = Path(__file__).with_name("ui_generation_fixture.json")
            destination.write_text(json.dumps({"receipt": accepted, "terminal": terminal},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"source": "real HTTP API + controlled provider", "receipt": accepted,
                              "terminal": terminal, "providerCalls": len(harness.provider.calls)},
                             ensure_ascii=False))
        finally:
            harness.close()


if __name__ == "__main__":
    main()
