#!/usr/bin/env python3
"""Narrow Codex-authorized command entry. Does not request or grant permissions itself."""
import argparse
import json
import re
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('probe')
    analyze=sub.add_parser('analyze')
    analyze.add_argument('session')
    analyze.add_argument('--timeout',type=int,default=600)
    args=parser.parse_args(argv)
    if args.action=='probe':
        from antigravity_backend import available_models,CLIError
        try:
            models=available_models()
            print(json.dumps(dict(status='ready',model_ids=sorted(models),model_calls=0)))
        except CLIError as exc:
            print(json.dumps(dict(status='blocked',reason=exc.reason,diagnostic=exc.diagnostic,model_calls=0)))
            return 2
        return 0
    if not re.fullmatch('[a-f0-9]{12}',args.session) or not 1<=args.timeout<=1800:
        parser.error('valid session ID and timeout 1..1800 required')
    # No arbitrary command, Python code, CLI flags, provider, model, data/cache path or paid mode.
    import va
    sys.argv=[str(va.ROOT/'scripts/va.py'),'analyze',args.session,'--timeout',str(args.timeout)]
    va.main()
    return 0


if __name__=='__main__':
    sys.exit(main())
