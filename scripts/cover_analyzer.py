#!/usr/bin/env python3
import argparse

from melinoe.workflows.bookworm import BookwormWorkflow

workflow = BookwormWorkflow()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a book cover and extract metadata")
    parser.add_argument("file", type=str, help="Path to the book cover image file")
    args = parser.parse_args()

    result = workflow.run(args.file)
    print(result)
