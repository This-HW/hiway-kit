"""Validate the LSP 3.17 wire shapes used by the read-only client.

Contract: https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/
Unknown extension fields are allowed; required fields and discriminators are not.
"""
from __future__ import annotations

from urllib.parse import urlsplit

MAX_ITEMS = 10000
MAX_SYMBOL_DEPTH = 64


class LspError(RuntimeError):
    pass


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise LspError("Invalid " + detail + "; result is unverified")


def integer(value, minimum=-2147483648, maximum=2147483647) -> bool:
    return type(value) is int and minimum <= value <= maximum


def uri(value) -> bool:
    try:
        return isinstance(value, str) and bool(urlsplit(value).scheme)
    except ValueError:
        return False


def position(value) -> bool:
    return (isinstance(value, dict) and integer(value.get("line"), 0)
            and integer(value.get("character"), 0))


def span(value) -> bool:
    if not isinstance(value, dict) or not position(value.get("start")) or not position(value.get("end")):
        return False
    start, end = value["start"], value["end"]
    return (start["line"], start["character"]) <= (end["line"], end["character"])


def contains(outer, inner) -> bool:
    def key(point):
        return point["line"], point["character"]
    return key(outer["start"]) <= key(inner["start"]) <= key(inner["end"]) <= key(outer["end"])


def location(value) -> bool:
    return isinstance(value, dict) and uri(value.get("uri")) and span(value.get("range"))


def items(value, detail: str) -> list:
    require(isinstance(value, list) and len(value) <= MAX_ITEMS, detail)
    return value


def validate_message(message) -> None:
    require(isinstance(message, dict) and message.get("jsonrpc") == "2.0", "JSON-RPC version/object")
    if "id" in message:
        identifier = message["id"]
        require(isinstance(identifier, str) or integer(identifier)
                or (identifier is None and "error" in message and "method" not in message), "JSON-RPC ID")
    if "method" in message:
        require(isinstance(message["method"], str) and "result" not in message and "error" not in message,
                "JSON-RPC method/result/error combination")
        require(isinstance(message.get("params", {}), dict), "LSP parameters")
    else:
        require("id" in message and (("result" in message) != ("error" in message)) and "params" not in message,
                "JSON-RPC response (no result or ambiguous result/error)")
        if "error" in message:
            error = message["error"]
            require(isinstance(error, dict) and integer(error.get("code"))
                    and isinstance(error.get("message"), str), "JSON-RPC error code/message")


def validate_diagnostics(value) -> list:
    for row in items(value, "diagnostics list"):
        require(isinstance(row, dict) and span(row.get("range")) and isinstance(row.get("message"), str),
                "Diagnostic range/message")
        if "severity" in row:
            require(integer(row["severity"], 1, 4), "Diagnostic severity")
        if "code" in row:
            require(isinstance(row["code"], str) or integer(row["code"]), "Diagnostic code")
        if "source" in row:
            require(isinstance(row["source"], str), "Diagnostic source")
        if "codeDescription" in row:
            require(isinstance(row["codeDescription"], dict) and uri(row["codeDescription"].get("href")),
                    "Diagnostic codeDescription")
        if "tags" in row:
            require(all(integer(tag, 1, 2) for tag in items(row["tags"], "Diagnostic tags")), "Diagnostic tag")
        if "relatedInformation" in row:
            for related in items(row["relatedInformation"], "Diagnostic relatedInformation"):
                require(isinstance(related, dict) and location(related.get("location"))
                        and isinstance(related.get("message"), str), "Diagnostic related information")
    return value


def validate_publish(params) -> None:
    require(isinstance(params, dict) and uri(params.get("uri")), "publishDiagnostics URI")
    if "version" in params:
        require(integer(params["version"]), "publishDiagnostics version")
    validate_diagnostics(params.get("diagnostics"))


def validate_pull_report(report, previous_result_id=None, previous_items=None) -> tuple[list, str | None]:
    require(isinstance(report, dict), "document diagnostic report")
    result_id = report.get("resultId")
    if "resultId" in report:
        require(isinstance(result_id, str), "diagnostic resultId")
    if report.get("kind") == "full":
        result = validate_diagnostics(report.get("items"))
    elif report.get("kind") == "unchanged":
        require(isinstance(result_id, str) and isinstance(previous_result_id, str)
                and previous_items is not None and "items" not in report, "unchanged diagnostic report without prior result")
        result = validate_diagnostics(previous_items)
    else:
        raise LspError("Invalid diagnostic report kind; result is unverified")
    # This client explicitly does not negotiate relatedDocumentSupport.
    require("relatedDocuments" not in report, "unnegotiated related diagnostic documents")
    return result, result_id


def validate_navigation(action: str, result) -> None:
    if result is None:
        return
    if action == "symbols":
        rows = items(result, "document symbols")
        shape = None
        pending = [(row, 0) for row in rows]
        count = 0
        while pending:
            row, depth = pending.pop()
            count += 1
            require(depth <= MAX_SYMBOL_DEPTH and count <= MAX_ITEMS, "document symbol budget")
            require(isinstance(row, dict) and isinstance(row.get("name"), str)
                    and integer(row.get("kind"), 1, 26), "document symbol name/kind")
            current = "flat" if "location" in row else "tree"
            require(shape is None or shape == current, "mixed document symbol variants")
            shape = current
            if current == "flat":
                require(location(row["location"]), "SymbolInformation location")
                if "containerName" in row:
                    require(isinstance(row["containerName"], str), "SymbolInformation containerName")
            else:
                require(span(row.get("range")) and span(row.get("selectionRange"))
                        and contains(row["range"], row["selectionRange"]), "DocumentSymbol ranges")
                if "detail" in row:
                    require(isinstance(row["detail"], str), "DocumentSymbol detail")
                if "children" in row:
                    pending.extend((child, depth + 1) for child in items(row["children"], "DocumentSymbol children"))
            if "deprecated" in row:
                require(type(row["deprecated"]) is bool, "symbol deprecated")
            if "tags" in row:
                require(all(integer(tag, 1, 1) for tag in items(row["tags"], "symbol tags")), "symbol tag")
        return
    if isinstance(result, dict):
        require(action == "definition" and location(result), "single definition Location")
        return
    rows = items(result, "navigation list")
    variant = None
    for row in rows:
        current = "location" if location(row) else "link"
        require(variant is None or variant == current, "mixed navigation variants")
        variant = current
        if current == "location":
            continue
        require(action == "definition" and isinstance(row, dict) and uri(row.get("targetUri"))
                and span(row.get("targetRange")) and span(row.get("targetSelectionRange"))
                and contains(row["targetRange"], row["targetSelectionRange"]), "LocationLink target")
        if "originSelectionRange" in row:
            require(span(row["originSelectionRange"]), "LocationLink originSelectionRange")
