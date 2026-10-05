"""Process-local audit: allow isolated production imports/TEMP SQL, deny real IO."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def establish_isolation(prefix="zqky-controlled-"):
    parent = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    os.environ["TEMP"] = os.environ["TMP"] = str(parent)
    tempfile.tempdir = str(parent)
    data = parent / "data"
    os.environ.update(ZQKY_DATA_DIR=str(data), ZQKY_ENV="test", PYTHONUTF8="1", ZQKY_KEEP_TEST_DATA="1")
    return parent


class AuditGuard:
    def __init__(self, allowed_temp, repository):
        self.allowed_temp, self.repository = Path(allowed_temp).resolve(), Path(repository).resolve()
        self.counts = dict(allowedProductionImports=0, allowedTempDatabaseConnections=0,
            allowedAsyncioInternalSocketPairs=0,
            forbiddenMainWithoutIsolation=0, forbiddenFormalEnvReads=0,
            forbiddenFormalDataReads=0, forbiddenDatabaseConnections=0, forbiddenNetworkAttempts=0)
        self.active = True

    def install(self):
        sys.addaudithook(self.audit)
        return self

    def audit(self, event, args):
        if not self.active:
            return
        if event == "import" and args:
            name = args[0]
            if type(name) is str and name.startswith("app."):
                self.counts["allowedProductionImports"] += 1
                if name == "app.main" and not (os.environ.get("ZQKY_ENV") == "test" and os.environ.get("PYTHONUTF8") == "1" and Path(os.environ.get("ZQKY_DATA_DIR", "")).resolve().is_relative_to(self.allowed_temp)):
                    self.counts["forbiddenMainWithoutIsolation"] += 1
                    raise PermissionError("app.main isolation missing")
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == ".env" or path.name.startswith(".env."):
                self.counts["forbiddenFormalEnvReads"] += 1
                raise PermissionError("credential file forbidden in controlled offline trial")
            formal = self.repository / "apps" / "api" / ".local-data"
            if path.is_relative_to(formal):
                self.counts["forbiddenFormalDataReads"] += 1
                raise PermissionError("formal data forbidden")
        if event == "sqlite3.connect" and args:
            database = str(args[0])
            if database.startswith("file:"):
                from urllib.parse import unquote
                database = unquote(database[5:].split("?",1)[0])
            path = Path(database).resolve()
            if path.is_relative_to(self.allowed_temp):
                self.counts["allowedTempDatabaseConnections"] += 1
            else:
                self.counts["forbiddenDatabaseConnections"] += 1
                raise PermissionError("only new TEMP SQL is permitted")
        if event in {"socket.connect", "socket.getaddrinfo"}:
            if event == "socket.connect":
                frame = sys._getframe(1)
                if frame.f_code.co_name == "_fallback_socketpair" and frame.f_globals.get("__name__") == "socket":
                    caller = frame.f_back
                    if caller is not None and caller.f_code.co_name == "_make_self_pipe" and str(caller.f_globals.get("__name__","")).startswith("asyncio."):
                        self.counts["allowedAsyncioInternalSocketPairs"] += 1
                        return
            self.counts["forbiddenNetworkAttempts"] += 1
            raise PermissionError("real network disabled for offline trial")

    def report(self):
        return {"isolationEstablishedBeforeProductionImport": True, "allowedTemp": str(self.allowed_temp),
            "environment": {k: os.environ.get(k) for k in ("ZQKY_DATA_DIR", "ZQKY_ENV", "PYTHONUTF8")},
            "credentialsFile": None, "mainImported": "app.main" in sys.modules, **self.counts}
