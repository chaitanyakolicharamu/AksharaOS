"""Fetch bounded, attributed source snapshots; failed refreshes keep old data intact."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import quote

import mwparserfromhell
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from knowledge.schema import Evidence, Record, load_sources, normalize, write_jsonl

USER_AGENT = "AksharaOS/0.2 (https://github.com/chaitanyakolicharamu/AksharaOS)"


class WikimediaClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get(self, url, params):
        for attempt in range(4):
            response = self.session.get(url, params=params, timeout=(10, 45))
            response.raise_for_status()
            payload = response.json()
            error = payload.get("error")
            if not error:
                return payload
            if error.get("code") != "maxlag" or attempt == 3:
                raise RuntimeError(f"Wikimedia API error: {error}")
            time.sleep(2**attempt)
        raise RuntimeError("Wikimedia retry exhausted")


def plain_definition(value: str) -> str:
    """Expand only well-understood inline templates; discard unresolved definitions."""
    code = mwparserfromhell.parse(value)
    for template in code.filter_templates(recursive=False):
        name = str(template.name).strip().lower()
        if name in {"l", "link", "m", "mention"} and template.has(2):
            replacement = str(
                template.get(3).value if template.has(3) else template.get(2).value
            )
        elif name in {
            "lb",
            "label",
            "context",
            "q",
            "qualifier",
            "gloss",
            "non-gloss definition",
            "ngd",
        }:
            args = [str(p.value) for p in template.params if str(p.name).isdigit()]
            if name in {"lb", "label", "context"}:
                args = args[1:]
            replacement = "(" + ", ".join(args) + ")"
        else:
            return ""
        code.replace(template, replacement)
    # Links to illustrations/categories are not definitions.
    for link in code.filter_wikilinks():
        if re.match(r"(?i)(file|image|category|వర్గం|దస్త్రం):", str(link.title)):
            code.remove(link)
    return normalize(code.strip_code()).strip("*#:; /-")


def definitions(wikitext: str, adapter: str) -> list[str]:
    if adapter == "wiktionary_en":
        match = re.search(r"(?ms)^==\s*Telugu\s*==\s*\n(.*?)(?=^==[^=]|\Z)", wikitext)
        if not match:
            return []
        return [
            text
            for line in match[1].splitlines()
            if re.match(r"^#+[^:*#]", line)
            if (text := plain_definition(line))
        ]
    # Telugu entries use both sections and definition-list labels. Keep semantics
    # and English glosses; never ingest the song/poem usage-example section.
    match = re.search(r"(?ms)^==\s*అర్థ[^=]*==\s*(.*?)(?=^==|\Z)", wikitext)
    found = []
    if match:
        for line in match[1].splitlines():
            if text := plain_definition(line):
                found.append(text)
    for line in wikitext.splitlines():
        if re.match(r"^\*\s*\[\[ఇంగ్లీషు\]\]", line):
            text = plain_definition(line.split(":", 1)[-1])
            if text and re.search(r"[A-Za-z]{2}", text):
                found.append("English: " + text)
    return found if match else []


def wiki_pages(client, source, limit, titles=None):
    base = dict(
        action="query",
        format="json",
        formatversion=2,
        maxlag=5,
        prop="revisions",
        rvprop="ids|timestamp|content",
        rvslots="main",
    )
    if titles:
        for i in range(0, min(len(titles), limit), 20):
            data = client.get(
                source.url, {**base, "titles": "|".join(titles[i : min(i + 20, limit)])}
            )
            yield from data.get("query", {}).get("pages", [])
        return
    continuation = {}
    seen = 0
    while seen < limit:
        params = dict(
            base,
            generator="categorymembers",
            gcmtitle=source.category,
            gcmtype="page",
            gcmnamespace=0,
            gcmlimit=min(50, limit - seen),
        )
        data = client.get(source.url, {**params, **continuation})
        pages = data.get("query", {}).get("pages", [])
        yield from pages
        seen += len(pages)
        if not data.get("continue") or not pages:
            break
        continuation = data["continue"]
        time.sleep(0.2)


def evidence(source, url, revision, retrieved_at):
    return Evidence(
        source_id=source.id,
        url=url,
        revision=str(revision),
        license=source.license,
        license_url=source.license_url,
        attribution=source.attribution,
        retrieved_at=retrieved_at,
    )


def wiktionary_records(pages, source, retrieved_at):
    for page in pages:
        if page.get("missing") or not page.get("revisions"):
            continue
        rev = page["revisions"][0]
        text = rev["slots"]["main"].get("content", "")
        values = definitions(text, source.adapter)
        if (
            not values
            or not re.fullmatch(r"[\u0c00-\u0c7f\s-]+", page["title"])
            or not re.search(r"[\u0c05-\u0c39\u0c58-\u0c61]", page["title"])
        ):
            continue
        url = (
            source.url.replace("api.php", "index.php")
            + f"?title={quote(page['title'])}&oldid={rev['revid']}"
        )
        yield Record(
            title=page["title"],
            text="; ".join(dict.fromkeys(values)),
            evidence=[evidence(source, url, rev["revid"], retrieved_at)],
        ).canonicalize()


def wikidata_records(client, source, limit, retrieved_at):
    query = (
        "SELECT DISTINCT ?lexeme WHERE { ?lexeme <http://purl.org/dc/terms/language> "
        "<http://www.wikidata.org/entity/Q8097> ; <http://www.w3.org/ns/lemon/ontolex#sense> ?sense . "
        "?sense <http://www.w3.org/2004/02/skos/core#definition> ?gloss . "
        f'FILTER(LANG(?gloss) IN ("te", "en")) }} ORDER BY ?lexeme LIMIT {int(limit)}'
    )
    result = client.get(
        "https://query.wikidata.org/sparql", {"query": query, "format": "json"}
    )
    ids = [
        r["lexeme"]["value"].rsplit("/", 1)[-1] for r in result["results"]["bindings"]
    ]
    for i in range(0, len(ids), 40):
        data = client.get(
            source.url,
            dict(
                action="wbgetentities",
                ids="|".join(ids[i : i + 40]),
                format="json",
                maxlag=5,
            ),
        )
        for entity in data.get("entities", {}).values():
            if entity.get("language") != "Q8097":
                continue
            title = entity.get("lemmas", {}).get("te", {}).get("value")
            if not title:
                continue
            for sense in entity.get("senses", []):
                glosses = [
                    v["value"]
                    for k, v in sense.get("glosses", {}).items()
                    if k in {"te", "en"}
                ]
                if not glosses:
                    continue
                url = (
                    "https://www.wikidata.org/w/index.php?title=Lexeme:"
                    f"{entity['id']}&oldid={entity['lastrevid']}#{sense['id']}"
                )
                yield Record(
                    title=title,
                    text="; ".join(glosses),
                    evidence=[evidence(source, url, entity["lastrevid"], retrieved_at)],
                ).canonicalize()


def ingest(source, output: Path, limit=300, titles=None, input_path=None, client=None):
    if not source.enabled or not source.reuse_approved:
        raise ValueError(f"Source {source.id} is disabled or needs reuse approval")
    now = datetime.now(timezone.utc).isoformat()
    client = client or WikimediaClient()
    if source.adapter == "local":
        if not input_path:
            raise ValueError(
                "Local sources require --input JSONL with title, text, url, revision"
            )
        rows = []
        for line in Path(input_path).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows.append(
                Record(
                    title=row["title"],
                    text=row["text"],
                    kind=row.get("kind", "passage"),
                    evidence=[evidence(source, row["url"], row["revision"], now)],
                ).canonicalize()
            )
    elif source.adapter == "wikidata":
        rows = list(wikidata_records(client, source, limit, now))
    else:
        rows = list(
            wiktionary_records(wiki_pages(client, source, limit, titles), source, now)
        )
    if not rows:
        raise ValueError(
            f"No usable records returned for {source.id}; previous snapshot retained"
        )
    # Repeated fetches of the same record are one record, not extra support.
    rows = list({row.id: row for row in rows}.values())
    write_jsonl(output, sorted(rows, key=lambda r: r.id))
    return {"source": source.id, "records": len(rows), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/sources.yaml"))
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--titles", type=Path, help="UTF-8 file, one title per line")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error("--limit must be 1..10000; use reviewed bounded snapshots")
    sources = load_sources(args.config)
    if args.source not in sources:
        parser.error("Unknown source")
    output = args.output or Path("data/knowledge/sources") / (args.source + ".jsonl")
    titles = (
        args.titles.read_text(encoding="utf-8").splitlines() if args.titles else None
    )
    print(
        json.dumps(
            ingest(sources[args.source], output, args.limit, titles, args.input),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
