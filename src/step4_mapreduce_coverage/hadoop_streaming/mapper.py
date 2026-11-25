#!/usr/bin/env python3
"""
Hadoop Streaming Mapper for Distributed BAM/SAM Coverage Computation.
Input from STDIN: Partition specification or SAM alignment lines.
Format:
  PARTITION\tchrom\tstart\tend\tsam_file_path
Emits to STDOUT:
  chrom\tstart\tend\tdepth
"""

import sys
import os
import re

# Add parent directory to path to import exact_coverage_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from step4_mapreduce_coverage.exact_coverage_engine import ExactCoverageEngine


def parse_sam_line(line: str):
    if line.startswith("@"):
        return None
    parts = line.strip().split("\t")
    if len(parts) < 11:
        return None
    return {
        "chrom": parts[2],
        "pos": int(parts[3]),
        "mapq": int(parts[4]),
        "cigar": parts[5],
        "flag": int(parts[1])
    }


def run_mapper():
    engine = ExactCoverageEngine(min_mapq=0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if parts[0] == "PARTITION" and len(parts) >= 5:
            chrom = parts[1]
            start = int(parts[2])
            end = int(parts[3])
            sam_path = parts[4]

            # Read matching reads from SAM file
            reads = []
            if os.path.exists(sam_path):
                with open(sam_path, "r") as f:
                    for s_line in f:
                        r = parse_sam_line(s_line)
                        if r and r["chrom"] == chrom and (r["pos"] < end and r["pos"] + 150 > start):
                            reads.append(r)

            _, bedgraph_entries, _ = engine.compute_exact_interval_coverage(reads, start, end)
            for bg_start, bg_end, depth in bedgraph_entries:
                sys.stdout.write(f"{chrom}\t{bg_start}\t{bg_end}\t{depth}\n")
        else:
            # Direct SAM stream mode
            r = parse_sam_line(line)
            if r:
                blocks = engine.get_aligned_blocks(r["pos"], r["cigar"])
                for b_start, b_end in blocks:
                    sys.stdout.write(f"{r['chrom']}\t{b_start}\t{b_end}\t1\n")


if __name__ == "__main__":
    run_mapper()
