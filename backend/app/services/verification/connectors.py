"""Issuer connectors. Every connector in this prototype is a MOCK.

A real integration would implement IssuerConnector against an issuer's API. The MOCK connector
reads seed/output/mock_issuer_data.json (generated with the synthetic documents) and can
simulate outages and timeouts. It never makes up a record: unknown references return None.
"""
import json
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings


class SourceUnavailable(Exception):
    """The issuer could not be reached (timeout, outage, missing data)."""


class IssuerConnector(ABC):
    code: str
    label: str
    is_mock: bool

    @abstractmethod
    def lookup(self, reference: str) -> dict | None:
        """Return the issuer's record for `reference`, None if it does not exist, or raise SourceUnavailable."""


class MockIssuerConnector(IssuerConnector):
    is_mock = True

    def __init__(self, code: str, label: str, data_path: Path):
        self.code = code
        self.label = label
        self.data_path = data_path

    def _records(self) -> dict:
        if not self.data_path.exists():
            raise SourceUnavailable(f"MOCK issuer data not found at {self.data_path.name}")
        try:
            return json.loads(self.data_path.read_text(encoding="utf-8")).get("records", {})
        except ValueError as exc:
            raise SourceUnavailable("MOCK issuer data is unreadable") from exc

    def lookup(self, reference: str) -> dict | None:
        record = self._records().get(reference)
        if record is None or record.get("issuer") != self.code:
            return None
        simulate = record.get("simulate")
        if simulate == "timeout":
            raise SourceUnavailable(f"{self.label} did not respond within 5 s (simulated timeout)")
        if simulate == "outage":
            raise SourceUnavailable(f"{self.label} is unavailable (simulated outage)")
        return record


ISSUERS = {
    "MOCK-FIRE": "MOCK State Fire Services registry",
    "MOCK-ACCREDITATION": "MOCK Accreditation Board registry",
    "MOCK-LAND-REGISTRY": "MOCK Land Registration office",
}

# Which issuer holds records for each document type. Other types have no issuer to check.
ISSUER_FOR_DOC_TYPE = {
    "fire_noc": "MOCK-FIRE",
    "accreditation_certificate": "MOCK-ACCREDITATION",
    "land_document": "MOCK-LAND-REGISTRY",
}


def get_connector(code: str) -> IssuerConnector | None:
    label = ISSUERS.get(code)
    if label is None:
        return None
    return MockIssuerConnector(code, label, Path(settings.mock_issuer_data_path))
