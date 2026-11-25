"""
Synthetic Genomic Alignment Data Generator.
Generates realistic SAM/BAM-like alignment datasets and target BED intervals
with configurable computational skew (hotspot read depth, CIGAR complexity, and indels)
to test and evaluate distributed Hadoop MapReduce coverage computation.
"""

import os
import random
import yaml
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


def generate_cigar_string(read_length: int, complexity_prob: float) -> Tuple[str, int, int]:
    """
    Generate a realistic CIGAR string with matches (M), insertions (I), deletions (D),
    and soft clipping (S). Returns (cigar_str, num_indels, num_clips).
    """
    if random.random() > complexity_prob:
        return f"{read_length}M", 0, 0
    
    # Generate complex alignment with indels/clips
    parts = []
    rem_len = read_length
    num_indels = 0
    num_clips = 0
    
    # Possible leading clip
    if random.random() < 0.2:
        clip = random.randint(5, 20)
        clip = min(clip, rem_len - 30)
        parts.append(f"{clip}S")
        rem_len -= clip
        num_clips += 1
        
    while rem_len > 30:
        match_len = random.randint(20, min(60, rem_len))
        parts.append(f"{match_len}M")
        rem_len -= match_len
        
        if rem_len > 10 and random.random() < 0.5:
            op = random.choice(['I', 'D'])
            op_len = random.randint(1, 4)
            if op == 'I':
                op_len = min(op_len, rem_len - 10)
                parts.append(f"{op_len}I")
                rem_len -= op_len
            else:
                parts.append(f"{op_len}D")
            num_indels += 1
            
    if rem_len > 0:
        parts.append(f"{rem_len}M")
        
    return "".join(parts), num_indels, num_clips


def generate_synthetic_dataset(config_path: str = "config/default_config.yaml",
                               output_dir: str = "data") -> Tuple[str, str]:
    """
    Generates synthetic alignment dataset (SAM format and compressed tabular format)
    along with target BED intervals according to config specifications.
    """
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    gen_cfg = config["genomics"]
    chrom = gen_cfg["chrom"]
    total_len = gen_cfg["region_length"]
    read_len = gen_cfg["mean_read_length"]
    base_depth = gen_cfg["depth_mean"]
    skew_hotspots = gen_cfg.get("skew_hotspots", [])

    os.makedirs(output_dir, exist_ok=True)
    sam_output_path = os.path.join(output_dir, "synthetic_alignments.sam")
    bed_output_path = os.path.join(output_dir, "test_regions.bed")
    summary_path = os.path.join(output_dir, "dataset_summary.csv")

    print(f"[*] Generating synthetic genomic dataset for {chrom} (Length: {total_len:,} bp)...")
    
    # Generate target BED intervals for static comparison
    chunk_size = gen_cfg["default_static_chunk_size"]
    bed_records = []
    for start in range(0, total_len, chunk_size):
        end = min(start + chunk_size, total_len)
        bed_records.append({"chrom": chrom, "start": start, "end": end, "name": f"region_{start}_{end}"})
    pd.DataFrame(bed_records).to_csv(bed_output_path, sep="\t", header=False, index=False)
    print(f"[+] Created target BED regions file: {bed_output_path} ({len(bed_records)} regions)")

    # Compute depth profile along the chromosome with skew hotspots
    # Baseline reads count = (total_len * base_depth) / read_len
    # We will simulate reads segment by segment
    read_id = 0
    sam_lines = [
        f"@HD\tVN:1.6\tSO:coordinate\n",
        f"@SQ\tSN:{chrom}\tLN:{total_len}\n",
        f"@PG\tID:GenomicSim\tPN:SyntheticDataGenerator\tVN:1.0\n"
    ]

    records = []
    step = 50000  # 50 kbp simulation step
    
    for seg_start in range(0, total_len, step):
        seg_end = min(seg_start + step, total_len)
        seg_len = seg_end - seg_start
        
        # Check if in hotspot
        multiplier = 1.0
        complexity_rate = 0.15
        for h_start, h_end, h_mult in skew_hotspots:
            if not (seg_end <= h_start or seg_start >= h_end):
                multiplier = max(multiplier, h_mult)
                complexity_rate = 0.65  # Higher alignment complexity in hotspots
                break
                
        effective_depth = base_depth * multiplier
        num_reads = int((seg_len * effective_depth) / read_len)
        
        # Generate reads in this segment
        pos_list = np.random.randint(seg_start, max(seg_start + 1, seg_end - read_len), size=num_reads)
        pos_list.sort()
        
        for pos in pos_list:
            read_id += 1
            qname = f"read_{read_id}"
            flag = random.choice([0, 16])  # 0: forward, 16: reverse
            mapq = int(np.clip(np.random.normal(55 if multiplier == 1.0 else 38, 8), 0, 60))
            cigar, n_indels, n_clips = generate_cigar_string(read_len, complexity_rate)
            
            # GC content variation: hotspots have higher GC skew
            gc_bias = 0.60 if multiplier > 1.5 else 0.45
            seq = "".join(random.choices(['G', 'C', 'A', 'T'], weights=[gc_bias/2, gc_bias/2, (1-gc_bias)/2, (1-gc_bias)/2], k=read_len))
            qual = "I" * read_len  # Phred quality 40
            
            sam_line = f"{qname}\t{flag}\t{chrom}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{seq}\t{qual}\n"
            sam_lines.append(sam_line)
            
            records.append({
                "read_id": read_id,
                "chrom": chrom,
                "pos": pos,
                "mapq": mapq,
                "cigar": cigar,
                "indels": n_indels,
                "clips": n_clips,
                "multiplier": multiplier
            })

    print(f"[+] Total simulated reads: {len(sam_lines) - 3:,} with realistic skew and hotspots.")
    
    with open(sam_output_path, "w") as f:
        f.writelines(sam_lines)
    print(f"[+] Wrote SAM alignment dataset to {sam_output_path}")

    df_summary = pd.DataFrame(records)
    df_summary.to_csv(summary_path, index=False)
    print(f"[+] Saved read alignment metadata summary to {summary_path}")

    return sam_output_path, bed_output_path


if __name__ == "__main__":
    generate_synthetic_dataset()
