"""
Feature Extraction for Genomic Workload Prediction.
Inspired by Lai et al. (2025) (LPA - Learning-based Parallel Acceleration).

Extracts computational complexity features using fast sampling from genomic intervals
including read count, read density, estimated depth, CIGAR operation complexity,
indel frequencies, mapping quality, and GC bias.
"""

import re
import random
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


class GenomicFeatureExtractor:
    def __init__(self, sampling_fraction: float = 0.05, seed: int = 42):
        """
        :param sampling_fraction: Fraction of reads / region sampled for ultrafast feature extraction (e.g., 0.05 = 5%)
        :param seed: Random seed for reproducibility
        """
        self.sampling_fraction = sampling_fraction
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def parse_cigar(self, cigar: str) -> Tuple[int, int, int, int]:
        """
        Parses a CIGAR string and returns (matches, insertions, deletions, clippings).
        """
        matches = 0
        insertions = 0
        deletions = 0
        clippings = 0

        pattern = re.compile(r'(\d+)([MIDNSHP=X])')
        for length, op in pattern.findall(cigar):
            length = int(length)
            if op in ('M', '=', 'X'):
                matches += length
            elif op == 'I':
                insertions += length
            elif op == 'D':
                deletions += length
            elif op in ('S', 'H'):
                clippings += length

        return matches, insertions, deletions, clippings

    def extract_features_from_reads(self,
                                    reads: List[Dict],
                                    chrom: str,
                                    start: int,
                                    end: int) -> Dict[str, float]:
        """
        Extract features from a list of read records falling inside the interval [start, end).
        """
        span = max(1, end - start)
        total_in_region = len(reads)

        if total_in_region == 0:
            return {
                "sampled_read_count": 0.0,
                "read_density": 0.0,
                "estimated_mean_depth": 0.0,
                "cigar_mismatch_rate": 0.0,
                "indel_frequency": 0.0,
                "mean_mapq": 60.0,
                "gc_content": 0.45,
                "region_span": float(span)
            }

        # Sampling step: ultrafast approximation without full processing
        sample_size = max(10, int(total_in_region * self.sampling_fraction))
        sample_size = min(sample_size, total_in_region)
        sampled_reads = random.sample(reads, sample_size)

        total_read_bp = 0
        total_mapq = 0
        total_indels = 0
        total_clips = 0
        total_gc = 0
        total_seq_len = 0

        for r in sampled_reads:
            mapq = r.get("mapq", 60)
            total_mapq += mapq

            cigar = r.get("cigar", "150M")
            matches, ins, dels, clips = self.parse_cigar(cigar)
            total_indels += (ins + dels)
            total_clips += clips

            seq = r.get("seq", "")
            if seq:
                seq_len = len(seq)
                total_seq_len += seq_len
                total_read_bp += seq_len
                gc_count = seq.count('G') + seq.count('C') + seq.count('g') + seq.count('c')
                total_gc += gc_count
            else:
                total_read_bp += matches

        # Scale sampled quantities to estimate full region metrics
        scaling_factor = total_in_region / sample_size
        estimated_total_reads = total_in_region
        estimated_mean_depth = (total_read_bp * scaling_factor) / span
        read_density = estimated_total_reads / span

        mean_mapq = total_mapq / sample_size
        indel_freq = (total_indels / sample_size)
        clip_rate = (total_clips / sample_size)
        gc_content = (total_gc / total_seq_len) if total_seq_len > 0 else 0.45

        # Alignment complexity metric combining indels, soft-clipping, and mapping ambiguity
        cigar_mismatch_rate = (indel_freq + 0.5 * clip_rate) / max(1.0, (total_read_bp / sample_size))

        return {
            "sampled_read_count": float(estimated_total_reads),
            "read_density": float(read_density),
            "estimated_mean_depth": float(estimated_mean_depth),
            "cigar_mismatch_rate": float(cigar_mismatch_rate),
            "indel_frequency": float(indel_freq),
            "mean_mapq": float(mean_mapq),
            "gc_content": float(gc_content),
            "region_span": float(span)
        }

    def extract_from_sam_file(self,
                              sam_file_path: str,
                              intervals: List[Tuple[str, int, int]]) -> pd.DataFrame:
        """
        Parses SAM alignment file and extracts features for each interval in the list.
        """
        # Bucket reads into intervals
        interval_reads: Dict[int, List[Dict]] = {i: [] for i in range(len(intervals))}
        
        # Build interval lookup for fast mapping
        import bisect
        sorted_intervals = sorted(enumerate(intervals), key=lambda x: (x[1][0], x[1][1]))
        starts = [item[1][1] for item in sorted_intervals]
        
        with open(sam_file_path, "r") as f:
            for line in f:
                if line.startswith("@"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) < 11:
                    continue
                
                r_chrom = parts[2]
                r_pos = int(parts[3])
                
                # Fast bisect lookup of candidate interval
                b_idx = bisect.bisect_right(starts, r_pos) - 1
                if b_idx >= 0 and b_idx < len(sorted_intervals):
                    orig_idx, (chrom, start, end) = sorted_intervals[b_idx]
                    if r_chrom == chrom and start <= r_pos < end:
                        read_info = {
                            "pos": r_pos,
                            "mapq": int(parts[4]),
                            "cigar": parts[5],
                            "seq": parts[9]
                        }
                        interval_reads[orig_idx].append(read_info)

        feature_rows = []
        for idx, (chrom, start, end) in enumerate(intervals):
            feats = self.extract_features_from_reads(interval_reads[idx], chrom, start, end)
            feats["region_id"] = idx
            feats["chrom"] = chrom
            feats["start"] = start
            feats["end"] = end
            feature_rows.append(feats)

        return pd.DataFrame(feature_rows)
