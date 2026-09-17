#!/usr/bin/env python3
"""Generate canonical UTM-tagged links without an AI or network call."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def campaign_url(base_url: str, product_slug: str, source: str, medium: str, campaign: str, content: str = "") -> str:
    parts = urlsplit(base_url.rstrip("/"))
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign,
        "utm_content": content or product_slug,
    })
    return urlunsplit((parts.scheme, parts.netloc, f"/product/{product_slug}", urlencode(query), ""))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("product_slug")
    parser.add_argument("source")
    parser.add_argument("medium")
    parser.add_argument("campaign")
    parser.add_argument("--content", default="")
    args = parser.parse_args()
    print(campaign_url(args.base_url, args.product_slug, args.source, args.medium, args.campaign, args.content))
