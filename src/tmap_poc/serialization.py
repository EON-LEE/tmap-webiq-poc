"""Shared parsing of the historical JSON answer contract."""

import json
import logging
from urllib.parse import urlparse


def citation_links(annotations):
    links, seen = [], set()
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        citation = annotation.get("url_citation", annotation)
        if not isinstance(citation, dict) or not isinstance(citation.get("url"), str):
            continue
        value = citation["url"]
        try:
            parsed = urlparse(value)
        except ValueError:
            logging.getLogger(__name__).warning("Ignoring a malformed citation URL; raw annotation is retained.")
            continue
        if (
            parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or value in seen
        ):
            continue
        title = citation.get("title")
        links.append({"url": value, "title": title if isinstance(title, str) and title else parsed.hostname})
        seen.add(value)
    return links


def parse_answer(content):
    if not content:
        return None, "empty content"
    text = content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            text = parts[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None, "no JSON object found"
    try:
        return json.loads(text[start:end + 1]), None
    except json.JSONDecodeError as exc:
        return None, f"json decode error: {exc}"
