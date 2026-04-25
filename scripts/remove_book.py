#!/usr/bin/env python3
import argparse

import melinoe.settings as settings
from melinoe.clients.meilisearch import MeilisearchClient

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove a book from Meilisearch by its ID")
    parser.add_argument("id", type=str, help="Book document ID in Meilisearch")
    args = parser.parse_args()

    client = MeilisearchClient(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
    client.delete_book(args.id)
    print(f"Removed: {args.id}")
