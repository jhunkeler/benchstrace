from argparse import ArgumentParser
from .benchmark import Benchmark
import sys


def prof_mode(args):
    result = Benchmark(args.COMMAND, passes=args.passes, setup=args.setup, teardown=args.teardown)

    print(f"Records: {result.count}")
    if args.output_file:
        result.save(args.output_file, clobber=args.clobber)
    return 0


def diff_mode(args):
    left = Benchmark()
    left.load(args.left)
    right = Benchmark()
    right.load(args.right)
    left.diff(right)

    print("\nSUMMARY\n")
    left.diff_average(right)
    left.diff_total(right)
    return 0


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_prof = subparsers.add_parser("prof")
    parser_prof.add_argument("-o", "--output_file", type=str)
    parser_prof.add_argument("-c", "--clobber", action='store_true')
    parser_prof.add_argument("-p", "--passes", type=int, default=1)
    parser_prof.add_argument("-s", "--setup", type=str)
    parser_prof.add_argument("-t", "--teardown", type=str)
    parser_prof.add_argument("COMMAND")
    parser_prof.set_defaults(func=prof_mode)

    parser_diff = subparsers.add_parser("diff")
    parser_diff.add_argument("left")
    parser_diff.add_argument("right")
    parser_diff.set_defaults(func=diff_mode)

    args = parser.parse_args()
    if len(sys.argv) < 2:
        parser.print_help()
        exit(0)

    args.func(args)

if __name__ == "__main__":
    sys.exit(main())
