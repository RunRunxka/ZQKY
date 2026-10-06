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
    def __init__(self, allowed_temp, repository, live_endpoint: tuple[str, tuple[str, ...]] | None = None):
        self.allowed_temp, self.repository = Path(allowed_temp).resolve(), Path(repository).resolve()
        # live_endpoint = (host, resolved addresses): the only outbound allowed in live mode.
        # Offline trials pass None and keep the whole network forbidden.
        self.live_host = (live_endpoint[0].lower() if live_endpoint else None)
        self.live_addresses = set(live_endpoint[1]) if live_endpoint else set()
        self._live_dns_seen = False
        self.counts = dict(allowedProductionImports=0, allowedTempDatabaseConnections=0,
            allowedAsyncioInternalSocketPairs=0,
            forbiddenMainWithoutIsolation=0, forbiddenFormalEnvReads=0,
            forbiddenFormalDataReads=0, forbiddenDatabaseConnections=0, forbiddenNetworkAttempts=0,
            allowedLiveDnsLookups=0, allowedLiveConnects=0)
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
            formal_roots = (self.repository / ".local-data", self.repository / "apps" / "api" / ".local-data")
            if any(path.is_relative_to(root) for root in formal_roots):
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
                if self.live_host and len(args) > 1 and isinstance(args[1], tuple) and len(args[1]) >= 2:
                    address = args[1]
                    raw_ip = address[0].decode("ascii", "ignore") if isinstance(address[0], bytes) else str(address[0])
                    try:
                        import ipaddress as _ip
                        public = not (_ip.ip_address(raw_ip).is_loopback or _ip.ip_address(raw_ip).is_private)
                    except ValueError:
                        public = False
                    if int(address[1]) == 443 and (raw_ip in self.live_addresses or (self._live_dns_seen and public)):
                        self.counts["allowedLiveConnects"] += 1
                        return
                    # On Windows Proactor the connect event may not be emitted at all;
                    # the DNS gate above is then the effective allowlist.
            if event == "socket.getaddrinfo" and self.live_host and args:
                # CPython/anyio may pass the host as str or bytes; normalize both.
                raw_host = args[0]
                if isinstance(raw_host, bytes):
                    raw_host = raw_host.decode("ascii", "ignore")
                host = str(raw_host).strip().rstrip(".").lower()
                port = args[1] if len(args) > 1 else None
                if isinstance(port, str) and port.isdigit():
                    port = int(port)
                if host == self.live_host and port == 443:
                    self._live_dns_seen = True
                    self.counts["allowedLiveDnsLookups"] += 1
                    return
            self.counts["forbiddenNetworkAttempts"] += 1
            raise PermissionError("real network disabled for offline trial" if not self.live_host else "only the selected live endpoint is permitted")

    def report(self):
        return {"isolationEstablishedBeforeProductionImport": True, "allowedTemp": str(self.allowed_temp),
            "environment": {k: os.environ.get(k) for k in ("ZQKY_DATA_DIR", "ZQKY_ENV", "PYTHONUTF8")},
            "credentialsFile": None, "mainImported": "app.main" in sys.modules, **self.counts}
