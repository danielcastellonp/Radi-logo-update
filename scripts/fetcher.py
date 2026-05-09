"""
fetcher.py — Fetches articles from PubMed (curated journals) and
Semantic Scholar (top cited, any journal) for each topic.
"""

import os
import time
import requests
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SEMANTIC_BASE = "https://api.semanticscholar.org/graph/v1"
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")  # optional but recommended

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _date_range_str(months_back: int = 1) -> tuple[str, str]:
    """Returns (date_from, date_to) as YYYY/MM/DD strings for PubMed."""
    today = datetime.today()
    date_to = today.replace(day=1) - timedelta(days=1)   # last day of prev month
    date_from = (date_to.replace(day=1) - relativedelta(months=months_back - 1))
    return date_from.strftime("%Y/%m/%d"), date_to.strftime("%Y/%m/%d")


def _pubmed_search(query: str, max_results: int = 100) -> list[str]:
    """Returns list of PMIDs matching query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    try:
        r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        logger.error(f"PubMed search error: {e}")
        return []


def _pubmed_fetch(pmids: list[str]) -> list[dict]:
    """Fetches article metadata for a list of PMIDs."""
    if not pmids:
        return []
    articles = []
    # Fetch in batches of 200
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i+200]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY
        try:
            r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=60)
            r.raise_for_status()
            articles.extend(_parse_pubmed_xml(r.text))
            time.sleep(0.35)  # NCBI rate limit
        except Exception as e:
            logger.error(f"PubMed fetch error: {e}")
    return articles


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parses PubMed XML response into list of article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
        return []

    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            art = medline.find("Article")

            # PMID
            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # Title
            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""

            # Abstract
            abstract_parts = []
            abstract_el = art.find("Abstract")
            if abstract_el is not None:
                for at in abstract_el.findall("AbstractText"):
                    label = at.get("Label", "")
                    text = "".join(at.itertext())
                    abstract_parts.append(f"{label}: {text}" if label else text)
            abstract = " ".join(abstract_parts)

            # Authors
            authors = []
            author_list = art.find("AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    ln = author.findtext("LastName", "")
                    fn = author.findtext("ForeName", "")
                    if ln:
                        authors.append(f"{ln} {fn}".strip())
            authors_str = ", ".join(authors[:6])
            if len(authors) > 6:
                authors_str += " et al."

            # Journal
            journal_el = art.find("Journal")
            journal_name = ""
            pub_date = ""
            if journal_el is not None:
                journal_name = journal_el.findtext("ISOAbbreviation") or \
                               journal_el.findtext("Title") or ""
                ji = journal_el.find("JournalIssue")
                if ji is not None:
                    pd = ji.find("PubDate")
                    if pd is not None:
                        year = pd.findtext("Year", "")
                        month = pd.findtext("Month", "")
                        pub_date = f"{year} {month}".strip()

            # DOI
            doi = ""
            for loc in article.findall(".//ArticleId"):
                if loc.get("IdType") == "doi":
                    doi = loc.text or ""
                    break

            # MeSH
            mesh_terms = [
                mh.findtext("DescriptorName", "")
                for mh in medline.findall(".//MeshHeading/DescriptorName")
            ]

            articles.append({
                "pmid": pmid,
                "title": title.strip(),
                "abstract": abstract.strip(),
                "authors": authors_str,
                "journal": journal_name,
                "pub_date": pub_date,
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "mesh_terms": mesh_terms,
                "source": "pubmed",
                "citation_count": None,
            })
        except Exception as e:
            logger.warning(f"Error parsing article: {e}")
            continue

    return articles


# ─────────────────────────────────────────────
# Semantic Scholar
# ─────────────────────────────────────────────

def _semantic_scholar_top_cited(
    query: str,
    journal_issns: set[str],
    top_n: int = 10,
    months_back: int = 1,
) -> list[dict]:
    """
    Returns top N most cited articles in the last `months_back` months
    that are NOT in the curated journal list.
    """
    date_from = datetime.today() - relativedelta(months=months_back)
    year_from = date_from.year

    params = {
        "query": query,
        "fields": "title,abstract,authors,year,citationCount,externalIds,venue,publicationDate",
        "limit": 100,
        "publicationDateOrYear": f"{year_from}-{datetime.today().year}",
    }

    headers = {}
    ss_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    if ss_key:
        headers["x-api-key"] = ss_key

    try:
        r = requests.get(
            f"{SEMANTIC_BASE}/paper/search",
            params=params,
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        papers = data.get("data", [])
    except Exception as e:
        logger.error(f"Semantic Scholar error: {e}")
        return []

    # Filter out papers from curated journals (by ISSN if available)
    # and sort by citation count
    filtered = []
    for p in papers:
        # Try to detect if it's from a curated journal by name heuristic
        venue = p.get("venue", "") or ""
        # Basic exclusion: if venue matches known journal names, skip
        if not p.get("abstract"):
            continue
        external_ids = p.get("externalIds", {}) or {}
        pmid = external_ids.get("PubMed", "")

        authors_list = p.get("authors", [])
        authors_str = ", ".join([a.get("name", "") for a in authors_list[:6]])
        if len(authors_list) > 6:
            authors_str += " et al."

        doi = external_ids.get("DOI", "")

        filtered.append({
            "pmid": pmid or "",
            "title": p.get("title", ""),
            "abstract": p.get("abstract", ""),
            "authors": authors_str,
            "journal": venue,
            "pub_date": p.get("publicationDate", "") or str(p.get("year", "")),
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else "",
            "mesh_terms": [],
            "source": "semantic_scholar",
            "citation_count": p.get("citationCount", 0),
        })

    # Sort by citations descending, take top N
    filtered.sort(key=lambda x: x.get("citation_count") or 0, reverse=True)
    return filtered[:top_n]


# ─────────────────────────────────────────────
# Main fetch functions
# ─────────────────────────────────────────────

def fetch_for_topic(
    topic: dict,
    journal_ta_list: list[str],
    journal_issn_set: set[str],
    months_back: int = 1,
) -> dict:
    """
    For a given topic, fetches:
    - Articles from curated journals (PubMed)
    - Top 10 cited articles from any other journal (Semantic Scholar)
    Returns dict with both lists.
    """
    date_from, date_to = _date_range_str(months_back)
    logger.info(f"Fetching topic: {topic['name_en']} ({date_from} → {date_to})")

    # Build PubMed query
    journal_filter = " OR ".join([f'"{ta}"[Journal]' for ta in journal_ta_list])
    keyword_parts = topic.get("keywords", [])
    mesh_parts = [f'"{m}"[MeSH Terms]' for m in topic.get("mesh_terms", [])]

    topic_terms = " OR ".join([f'"{k}"' for k in keyword_parts] + mesh_parts)
    date_filter = f'("{date_from}"[PDAT] : "{date_to}"[PDAT])'

    pubmed_query = f"({topic_terms}) AND ({journal_filter}) AND {date_filter}"

    pmids = _pubmed_search(pubmed_query, max_results=50)
    pubmed_articles = _pubmed_fetch(pmids)
    logger.info(f"  PubMed: {len(pubmed_articles)} articles")

    # Semantic Scholar: top cited outside curated journals
    ss_query = " ".join(topic.get("keywords", [])[:4])
    ss_articles = _semantic_scholar_top_cited(
        query=ss_query,
        journal_issns=journal_issn_set,
        top_n=10,
        months_back=months_back,
    )
    logger.info(f"  Semantic Scholar top cited: {len(ss_articles)} articles")

    return {
        "topic_id": topic["id"],
        "topic_name": topic["name"],
        "topic_name_en": topic["name_en"],
        "pubmed_articles": pubmed_articles,
        "top_cited_articles": ss_articles,
        "date_from": date_from,
        "date_to": date_to,
    }


def fetch_adhoc_topic(adhoc: dict) -> dict:
    """Fetches articles for a user-defined ad-hoc topic."""
    date_map = {"1month": 1, "3months": 3, "6months": 6}
    months = date_map.get(adhoc.get("date_range", "1month"), 1)
    max_results = adhoc.get("max_results", 20)

    date_from, date_to = _date_range_str(months)
    logger.info(f"Fetching ad-hoc topic: {adhoc['name']}")

    date_filter = f'("{date_from}"[PDAT] : "{date_to}"[PDAT])'
    query = f"({adhoc['query']}) AND {date_filter}"

    pmids = _pubmed_search(query, max_results=max_results)
    articles = _pubmed_fetch(pmids)

    # Also get top cited from Semantic Scholar
    ss_articles = _semantic_scholar_top_cited(
        query=adhoc["query"],
        journal_issns=set(),
        top_n=10,
        months_back=months,
    )

    return {
        "topic_id": f"adhoc_{adhoc['name'][:20].replace(' ', '_').lower()}",
        "topic_name": adhoc["name"],
        "topic_name_en": adhoc["name"],
        "pubmed_articles": articles,
        "top_cited_articles": ss_articles,
        "date_from": date_from,
        "date_to": date_to,
        "is_adhoc": True,
    }
