"""Validate a RAG evaluation contract bundle without calling models."""

import argparse

from eval.contract_v1 import load_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    args = parser.parse_args()
    bundle = load_bundle(args.bundle)
    print(
        f"valid: {len(bundle['test_cases'])} cases, "
        f"run_id={bundle['run']['run_id']}, conclusion={bundle['report']['conclusion']}"
    )


if __name__ == "__main__":
    main()
