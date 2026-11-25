"""
Exact BAM Coverage Engine.
Inspired by Yu & Shi (2024) (PanDepth) and Samaddar et al. (2019).

Computes exact per-base genomic coverage depth using a difference-array line sweep algorithm.
Collapses contiguous identical depth regions into BedGraph format, and computes
exact summary statistics (mean depth, breadth of coverage >= 1x, >= 10x, >= 30x).
"""

import re
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


class ExactCoverageEngine:
    def __init__(self, min_mapq: int = 0, exclude_flags: int = 3844):
        """
        :param min_mapq: Minimum mapping quality threshold to include read
        :param exclude_flags: Standard SAM flags to exclude (unmapped, secondary, qc-fail, dup)
        """
        self.min_mapq = min_mapq
        self.exclude_flags = exclude_flags

    @staticmethod
    def get_aligned_blocks(pos: int, cigar: str) -> List[Tuple[int, int]]:
        """
        Interprets CIGAR operations to identify contiguous reference-aligned segments.
        Fast-paths common single-match CIGAR strings (e.g. '150M') without regex.
        """
        if cigar.endswith("M") and cigar[:-1].isdigit():
            return [(pos, pos + int(cigar[:-1]))]

        blocks = []
        curr_pos = pos
        pattern = re.compile(r'(\d+)([MIDNSHP=X])')
        
        for length_str, op in pattern.findall(cigar):
            length = int(length_str)
            if op in ('M', '=', 'X'):
                blocks.append((curr_pos, curr_pos + length))
                curr_pos += length
            elif op in ('D', 'N'):
                curr_pos += length
            elif op in ('I', 'S', 'H', 'P'):
                pass
                
        if not blocks:
            blocks.append((pos, pos + 150))
            
        return blocks

    def compute_exact_interval_coverage(self,
                                        reads: List[Dict],
                                        interval_start: int,
                                        interval_end: int) -> Tuple[np.ndarray, List[Tuple[int, int, int]], Dict[str, float]]:
        """
        Computes exact per-base coverage in [interval_start, interval_end) using
        difference array prefix sum (PanDepth / Mosdepth algorithm in O(N_reads + L_interval)).
        """
        span = interval_end - interval_start
        if span <= 0:
            return np.zeros(0, dtype=np.int32), [], {}

        diff = np.zeros(span + 1, dtype=np.int32)

        valid_reads_count = 0
        for r in reads:
            flag = r.get("flag", 0)
            if flag & self.exclude_flags:
                continue

            mapq = r.get("mapq", 60)
            if mapq < self.min_mapq:
                continue

            pos = r.get("pos", 0)
            blocks = r.get("blocks")
            if blocks is None:
                cigar = r.get("cigar", "150M")
                blocks = self.get_aligned_blocks(pos, cigar)
                r["blocks"] = blocks

            for b_start, b_end in blocks:
                # Overlap with [interval_start, interval_end)
                overlap_start = max(interval_start, b_start)
                overlap_end = min(interval_end, b_end)

                if overlap_start < overlap_end:
                    idx_start = overlap_start - interval_start
                    idx_end = overlap_end - interval_start
                    diff[idx_start] += 1
                    diff[idx_end] -= 1
                    valid_reads_count += 1

        # Prefix sum calculates exact depth at each base
        base_depths = np.cumsum(diff[:-1])

        # Convert to compressed BedGraph format
        bedgraph_entries = self.compress_to_bedgraph(base_depths, interval_start)

        # Calculate exact coverage summary statistics
        mean_depth = float(np.mean(base_depths))
        bases_ge_1x = float(np.mean(base_depths >= 1)) * 100.0
        bases_ge_10x = float(np.mean(base_depths >= 10)) * 100.0
        bases_ge_30x = float(np.mean(base_depths >= 30)) * 100.0
        max_depth = int(np.max(base_depths)) if len(base_depths) > 0 else 0

        metrics = {
            "interval_span": span,
            "reads_processed": valid_reads_count,
            "mean_coverage_depth": round(mean_depth, 2),
            "max_coverage_depth": max_depth,
            "pct_bases_ge_1x": round(bases_ge_1x, 2),
            "pct_bases_ge_10x": round(bases_ge_10x, 2),
            "pct_bases_ge_30x": round(bases_ge_30x, 2)
        }

        return base_depths, bedgraph_entries, metrics

    @staticmethod
    def compress_to_bedgraph(depth_array: np.ndarray, interval_start: int) -> List[Tuple[int, int, int]]:
        """
        Run-length encodes base-level depths into contiguous BedGraph intervals: (start, end, depth).
        """
        if len(depth_array) == 0:
            return []

        entries = []
        curr_val = depth_array[0]
        run_start = 0

        for i in range(1, len(depth_array)):
            if depth_array[i] != curr_val:
                entries.append((interval_start + run_start, interval_start + i, int(curr_val)))
                curr_val = depth_array[i]
                run_start = i

        entries.append((interval_start + run_start, interval_start + len(depth_array), int(curr_val)))
        return entries

    @staticmethod
    def verify_correctness(ref_depths: np.ndarray, test_depths: np.ndarray) -> bool:
        """
        Validates exact equivalence between two coverage depth arrays.
        Returns True if 100% of base positions have identical depths.
        """
        if len(ref_depths) != len(test_depths):
            return False
        return bool(np.array_equal(ref_depths, test_depths))
