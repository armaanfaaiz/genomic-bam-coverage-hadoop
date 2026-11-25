#!/usr/bin/env python3
"""
Hadoop Streaming Reducer for Distributed BAM Coverage Computation.
Input from STDIN (Hadoop sort & shuffle):
  chrom\tstart\tend\tdepth
Emits to STDOUT (Final exact BedGraph format):
  chrom\tstart\tend\taggregated_depth
"""

import sys


def run_reducer():
    current_chrom = None
    current_start = None
    current_end = None
    current_depth = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 4:
            continue

        chrom = parts[0]
        start = int(parts[1])
        end = int(parts[2])
        depth = int(parts[3])

        # If adjacent interval has identical depth on the same chromosome, merge them
        if (current_chrom == chrom and
            current_end == start and
            current_depth == depth):
            current_end = end
        else:
            if current_chrom is not None:
                sys.stdout.write(f"{current_chrom}\t{current_start}\t{current_end}\t{current_depth}\n")
            current_chrom = chrom
            current_start = start
            current_end = end
            current_depth = depth

    if current_chrom is not None:
        sys.stdout.write(f"{current_chrom}\t{current_start}\t{current_end}\t{current_depth}\n")


if __name__ == "__main__":
    run_reducer()
