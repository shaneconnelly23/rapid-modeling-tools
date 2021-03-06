"""
Copyright (C) 2020 by the Georgia Tech Research Institute (GTRI)
This software may be modified and distributed under the terms of
the BSD 3-Clause license. See the LICENSE file for details.
"""

import argparse

from .commands import compare_md_model, create_md_model
from ._version import __version__


def main():
    """
    Command line entry function
    :return:
    """

    print("Modeling the Model")

    parser = argparse.ArgumentParser(
        description="A simple CLI for parsing an Excel Workbook and "
        "generating SysML Graph JSON instructions to be used "
        "with the Player Piano."
    )

    parser.add_argument(
        "-c",
        "--create",
        nargs="?",
        help="Create a JSON file for Player Piano to use to create a MagicDraw Diagram",
        const=True,
    )

    parser.add_argument(
        "-C",
        "--compare",
        nargs="?",
        help=(
            "Compare a baseline Excel File with a collection of modified Excel Files."
            + " Must supply the original file first and then the changes"
        ),
        const=True,
    )

    parser.add_argument(
        "-i", "--input", nargs="*", help="Path to Excel Workbook(s)", type=str
    )

    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path/Directory where the JSON file(s) should be placed."
            + " Default behavior will place the JSON in the input location"
        ),
        type=str,
    )

    parser.add_argument(
        "-O",
        "--original",
        help="The original file to which the comparison will be run against.",
        type=str,
    )

    parser.add_argument(
        "-U",
        "--updated",
        nargs="+",
        help="Modified Excel files to be compared to the Original.",
        type=str,
    )

    parser.add_argument(
        "-p",
        "--pattern",
        nargs="*",
        help="Provide the path to the accompanying pattern JSON.",
        type=str,
    )

    parser.add_argument(
        "-v", "--version", help="version information", action="store_true"
    )

    args = parser.parse_args()
    if args.version:
        return __version__
    elif args.create:
        return create_md_model(args.input, args.pattern, args.output)
    elif args.compare:
        inputs = [args.original]
        inputs.extend(args.updated)
        return compare_md_model(inputs, args.pattern, args.output)
    else:
        return "Not a valid input argument. Choose from create or compare"


if __name__ == "__main__":
    main()
