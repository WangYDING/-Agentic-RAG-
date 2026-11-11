"""Offline governance commands; no formal execution or model-building command."""
import argparse
import json

from eval.decision_v1 import sign_assessment, verify_assessment
from eval.fingerprints_v1 import write_json
from eval.freeze_v1 import precheck, read_json
from eval.review_workflow_v1 import import_reviews, load_revision, export_review_template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("precheck")
    check.add_argument("freeze")
    check.add_argument("--output")
    review = sub.add_parser("import-reviews")
    review.add_argument("run")
    review.add_argument("packet")
    review.add_argument("--output", required=True)
    review.add_argument("--parent")
    template = sub.add_parser("export-review-template")
    template.add_argument("run")
    template.add_argument("--output", required=True)
    template.add_argument("--parent")
    sign = sub.add_parser("sign")
    sign.add_argument("run")
    sign.add_argument("--revision")
    sign.add_argument("--signer-json", required=True)
    sign.add_argument("--output", required=True)
    for command in ("verify-review", "verify-assessment"):
        sub.add_parser(command).add_argument("directory")
    args = parser.parse_args()
    if args.command == "precheck":
        result = precheck(read_json(args.freeze))
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False))
        if not result["eligible"]:
            raise SystemExit(2)
    elif args.command == "export-review-template":
        export_review_template(args.run, args.output, parent=args.parent)
        print("draft exported; reviewer identity, timestamp, labels and reasons must be filled")
    elif args.command == "import-reviews":
        state = import_reviews(args.run, args.packet, args.output, parent=args.parent)
        print(json.dumps({"reviews": len(state["reviews"]), "disputes": len(state["disputes"])}))
    elif args.command == "sign":
        result = sign_assessment(args.run, args.output, signer=read_json(args.signer_json), revision=args.revision)
        print(json.dumps({"conclusion": result["conclusion"], "purpose": result["purpose"]}))
    elif args.command == "verify-review":
        load_revision(args.directory)
        print("review lineage verified")
    else:
        result = verify_assessment(args.directory)
        print(result["conclusion"] + ": assessment lineage verified")


if __name__ == "__main__":
    main()
