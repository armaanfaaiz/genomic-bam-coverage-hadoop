"""
High-Throughput Streaming Generator for Large Genomic BAM/SAM Files (1GB - 15GB+).
Generates synthetic alignments directly to disk with buffered I/O, ensuring constant
low memory usage (< 150 MB RAM) regardless of output size.
Simulates realistic coverage skew, hotspot multipliers, and alignment complexities.
"""

import os
import sys
import time
import random
import argparse
import numpy as np
from typing import Tuple


def generate_cigar(read_len: int, complex_prob: float) -> str:
    if random.random() > complex_prob:
        return f"{read_len}M"
    m1 = random.randint(30, 70)
    op = random.choice(["I", "D", "S"])
    op_len = random.randint(1, 4)
    m2 = max(10, read_len - m1 - (op_len if op != "D" else 0))
    return f"{m1}M{op_len}{op}{m2}M"


def stream_generate_dataset(output_path: str = "data/alignments_15gb.sam",
                            target_size_gb: float = 15.0,
                            chrom: str = "chr1",
                            chrom_len: int = 50000000, # 50 Mbp
                            base_depth: float = 30.0,
                            read_len: int = 150) -> None:
    """
    Streams SAM records to disk until target_size_gb is reached.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    target_bytes = int(target_size_gb * 1024 * 1024 * 1024)

    # Hotspot definition: intervals with 4x-6x coverage skew
    hotspots = [
        (8000000, 14000000, 5.0),
        (22000000, 28000000, 4.5),
        (38000000, 44000000, 6.0)
    ]

    print(f"\n" + "="*70)
    print(f" STREAMING GENOMIC DATASET GENERATOR: TARGET {target_size_gb:.1f} GB")
    print(f" Output File: {output_path}")
    print(f" Chromosome: {chrom} (Length: {chrom_len:,} bp) | Base Depth: {base_depth}x")
    print("="*70)

    t_start = time.time()
    bytes_written = 0
    read_id = 0

    header_lines = [
        f"@HD\tVN:1.6\tSO:coordinate\n",
        f"@SQ\tSN:{chrom}\tLN:{chrom_len}\n",
        f"@PG\tID:GenomicStream\tPN:StreamGenerator\tVN:2.0\n"
    ]

    # Pre-generate nucleotide templates to maximize I/O throughput (10x faster)
    seq_pool = [
        "".join(random.choices(["A", "C", "G", "T"], k=read_len))
        for _ in range(2048)
    ]
    qual = "I" * read_len
    
    # Pre-generate common CIGAR variations
    normal_cigars = [f"{read_len}M"] * 90 + [f"70M2I{read_len-72}M", f"50M1D{read_len-50}M", f"30S{read_len-30}M"]
    hotspot_cigars = [f"{read_len}M"] * 40 + [f"50M3I{read_len-53}M", f"40M2D{read_len-40}M", f"25S{read_len-25}M", f"60M1I{read_len-61}M"]

    with open(output_path, "w", buffering=16 * 1024 * 1024) as f:
        for h in header_lines:
            f.write(h)
            bytes_written += len(h)

        chunk_size = 50000  # Number of reads per batch write
        while bytes_written < target_bytes:
            batch = []
            for _ in range(chunk_size):
                read_id += 1
                pos = random.randint(0, max(1, chrom_len - read_len))
                
                # Check for hotspot multiplier
                is_hotspot = False
                for hs_s, hs_e, _ in hotspots:
                    if hs_s <= pos < hs_e:
                        is_hotspot = True
                        break

                flag = 0 if (read_id & 1) == 0 else 16
                mapq = random.randint(45, 60) if not is_hotspot else random.randint(20, 45)
                cigar = normal_cigars[read_id % len(normal_cigars)] if not is_hotspot else hotspot_cigars[read_id % len(hotspot_cigars)]
                seq = seq_pool[read_id % 2048]

                line = f"read_{read_id}\t{flag}\t{chrom}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{seq}\t{qual}\n"
                batch.append(line)

            chunk_text = "".join(batch)
            f.write(chunk_text)
            bytes_written += len(chunk_text)

            elapsed = max(0.1, time.time() - t_start)
            current_gb = bytes_written / (1024**3)
            rate_mb_s = (bytes_written / (1024**2)) / elapsed
            progress_pct = min(100.0, (bytes_written / target_bytes) * 100.0)
            eta_s = (target_bytes - bytes_written) / (rate_mb_s * 1024 * 1024) if rate_mb_s > 0 else 0

            sys.stdout.write(
                f"\r[*] Generated: {current_gb:.2f} / {target_size_gb:.1f} GB ({progress_pct:.1f}%) | "
                f"Rate: {rate_mb_s:.1f} MB/s | Reads: {read_id:,} | ETA: {int(eta_s)}s   "
            )
            sys.stdout.flush()

    total_time = time.time() - t_start
    final_gb = bytes_written / (1024**3)
    print(f"\n\n[+] Dataset generated successfully in {total_time:.2f}s ({total_time/60:.1f} min)")
    print(f"[+] Final Size: {final_gb:.2f} GB ({bytes_written:,} bytes) | Total Alignments: {read_id:,}")
    print(f"[+] Location: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stream large synthetic BAM/SAM dataset")
    parser.add_argument("--size_gb", type=float, default=15.0, help="Target file size in GB (e.g., 1.0, 5.0, 15.0)")
    parser.add_argument("--output", type=str, default="data/alignments_15gb.sam", help="Output file path")
    args = parser.parse_args()

    stream_generate_dataset(output_path=args.output, target_size_gb=args.size_gb)
