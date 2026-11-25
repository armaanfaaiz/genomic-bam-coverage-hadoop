"""
Static Partitioner (Baseline).
Standard genomic partitioning by fixed coordinate chunk size (e.g., 100 kbp).
Serves as the traditional baseline that causes stragglers in skewed regions.
"""

from typing import Dict, List, Tuple
import pandas as pd


class StaticPartitioner:
    def __init__(self, chunk_size: int = 100000):
        """
        :param chunk_size: Fixed genomic window size in base pairs (default: 100,000 bp)
        """
        self.chunk_size = chunk_size

    def partition(self, chrom: str, start: int, end: int) -> List[Dict]:
        """
        Divides [start, end) into uniform, fixed-size chunks.
        """
        partitions = []
        part_id = 0
        curr_start = start
        
        while curr_start < end:
            curr_end = min(curr_start + self.chunk_size, end)
            partitions.append({
                "partition_id": f"static_{part_id:04d}",
                "chrom": chrom,
                "start": curr_start,
                "end": curr_end,
                "span": curr_end - curr_start,
                "type": "static"
            })
            part_id += 1
            curr_start = curr_end
            
        return partitions

    def partition_to_dataframe(self, chrom: str, start: int, end: int) -> pd.DataFrame:
        """
        Returns partitions as a pandas DataFrame.
        """
        return pd.DataFrame(self.partition(chrom, start, end))
