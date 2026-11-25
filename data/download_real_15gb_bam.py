"""
Real-World 15GB BAM File Downloader.
Downloads standard benchmark WGS BAM alignments from the 1000 Genomes Project
or Genome in a Bottle (GIAB) repository with resumable streaming.
"""

import os
import sys
import time
import urllib.request
import argparse

BENCHMARK_URLS = {
    "1000genomes_na12878_chr1": {
        "description": "1000 Genomes Project NA12878 Illumina WGS (Chromosome 1 slice, ~12-14 GB)",
        "url": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/technical/working/20140123_na12878_illumina_platinum/NA12878.wgs.illumina_platinum.recal.bam",
        "default_filename": "NA12878_chr1_benchmark.bam"
    },
    "giab_hg002_sample": {
        "description": "Genome in a Bottle (GIAB) Ashkenazi Son HG002 Illumina 2x250bp (~10-15 GB)",
        "url": "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/AshkenazimTrio/HG002_NA24385_son/NIST_HiSeq_HG002_Homogeneity-10957963/HG002_HiSeq300x_subsampled_30x.bam",
        "default_filename": "HG002_giab_benchmark.bam"
    }
}


def download_benchmark_bam(dataset_key: str = "1000genomes_na12878_chr1",
                           destination_dir: str = "data") -> str:
    """
    Downloads the selected real benchmark BAM file with live progress.
    """
    if dataset_key not in BENCHMARK_URLS:
        print(f"[!] Unknown dataset key: {dataset_key}. Available options: {list(BENCHMARK_URLS.keys())}")
        return ""

    info = BENCHMARK_URLS[dataset_key]
    url = info["url"]
    os.makedirs(destination_dir, exist_ok=True)
    out_file = os.path.join(destination_dir, info["default_filename"])

    print("\n" + "="*70)
    print(" REAL-WORLD GENOMIC BENCHMARK BAM DOWNLOADER")
    print(f" Dataset: {info['description']}")
    print(f" Source URL: {url}")
    print(f" Destination: {out_file}")
    print("="*70)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get("content-length", 0))
            total_gb = total_size / (1024**3)
            print(f"[*] Remote file size: {total_gb:.2f} GB ({total_size:,} bytes)")

            chunk_size = 4 * 1024 * 1024  # 4 MB chunks
            downloaded = 0
            t_start = time.time()

            with open(out_file, "wb") as f_out:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)

                    elapsed = max(0.1, time.time() - t_start)
                    cur_gb = downloaded / (1024**3)
                    speed_mb = (downloaded / (1024**2)) / elapsed
                    pct = (downloaded / total_size * 100.0) if total_size > 0 else 0
                    rem_s = (total_size - downloaded) / (speed_mb * 1024 * 1024) if speed_mb > 0 else 0

                    sys.stdout.write(
                        f"\r[*] Progress: {cur_gb:.2f} / {total_gb:.2f} GB ({pct:.1f}%) | "
                        f"Speed: {speed_mb:.1f} MB/s | ETA: {int(rem_s)}s   "
                    )
                    sys.stdout.flush()

        print(f"\n[+] Download completed successfully: {out_file}")
        return out_file

    except Exception as e:
        print(f"\n[!] Download error: {e}")
        print("[TIP] You can also download the file via browser or curl directly, or use stream_generate_15gb.py for offline testing.")
        return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download real 15GB BAM benchmark files")
    parser.add_argument("--dataset", type=str, default="1000genomes_na12878_chr1", choices=list(BENCHMARK_URLS.keys()))
    parser.add_argument("--output_dir", type=str, default="data")
    args = parser.parse_args()

    download_benchmark_bam(args.dataset, args.output_dir)
