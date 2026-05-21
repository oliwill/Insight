__all__ = ["MaterialInput", "EvidenceExtractor", "EvidenceItem"]


def __getattr__(name):
    if name == "MaterialInput":
        from .ingest import MaterialInput
        return MaterialInput
    if name in {"EvidenceExtractor", "EvidenceItem"}:
        from .evidence import EvidenceExtractor, EvidenceItem
        return {"EvidenceExtractor": EvidenceExtractor, "EvidenceItem": EvidenceItem}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
