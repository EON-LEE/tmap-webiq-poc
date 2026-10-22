"""Safe citation links from service annotations."""

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
