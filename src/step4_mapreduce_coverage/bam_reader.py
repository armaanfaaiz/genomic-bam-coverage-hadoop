"""
Pure-Python BAM and BGZF Parser for Windows.
Requires zero external C libraries (no pysam/samtools dependency required).
Parses standard BAM format specifications (HTSlib/SAMtools) directly.
"""

import os
import zlib
import struct
from typing import Generator, Dict, Any, Tuple, List

DNA_BASES = "=ACMGRSVTWYHKDBN"
CIGAR_OPS = "MIDNSHP=X"

class BGZFStreamReader:
    """
    Decompresses BGZF (Blocked GNU Zip Format) blocks on the fly with constant memory.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def read_blocks(self) -> Generator[bytes, None, None]:
        with open(self.filepath, "rb") as f:
            while True:
                header = f.read(10)
                if not header or len(header) < 10:
                    break

                # ID1=0x1f, ID2=0x8b, CM=8, FLG=4 (FEXTRA)
                if header[0] != 0x1f or header[1] != 0x8b or header[2] != 0x08 or (header[3] & 0x04) == 0:
                    break

                xlen_bytes = f.read(2)
                if len(xlen_bytes) < 2:
                    break
                xlen = struct.unpack("<H", xlen_bytes)[0]
                extra = f.read(xlen)
                if len(extra) < xlen:
                    break

                # Parse BGZF subfield 'BC'
                idx = 0
                bsize = 0
                while idx < len(extra) - 3:
                    si1, si2 = extra[idx], extra[idx+1]
                    slen = struct.unpack("<H", extra[idx+2:idx+4])[0]
                    if si1 == 66 and si2 == 67 and slen == 2:
                        bsize = struct.unpack("<H", extra[idx+4:idx+6])[0]
                        break
                    idx += 4 + slen

                if bsize == 0:
                    break

                cdata_len = (bsize + 1) - xlen - 12 - 8
                if cdata_len <= 0:
                    break

                cdata = f.read(cdata_len)
                trailer = f.read(8)
                if len(cdata) < cdata_len or len(trailer) < 8:
                    break

                try:
                    decomp = zlib.decompress(cdata, -zlib.MAX_WBITS)
                    yield decomp
                except Exception:
                    continue


class RealBAMParser:
    """
    Parses real binary BAM alignments into standardized record dictionaries.
    """
    def __init__(self, bam_path: str):
        self.bam_path = bam_path
        self.ref_names: List[str] = []
        self.ref_lengths: List[int] = []
        self.header_text = ""
        self._parse_header()

    def _parse_header(self):
        bgzf = BGZFStreamReader(self.bam_path)
        block_gen = bgzf.read_blocks()
        buf = bytearray()

        while len(buf) < 65536:
            try:
                buf.extend(next(block_gen))
            except StopIteration:
                break

        if len(buf) < 8:
            return

        magic = bytes(buf[:4])
        offset = 4
        l_text = struct.unpack("<i", buf[offset:offset+4])[0]
        offset += 4

        while len(buf) < offset + l_text + 4:
            try:
                buf.extend(next(block_gen))
            except StopIteration:
                break

        self.header_text = buf[offset:offset+l_text].decode("utf-8", errors="replace")
        offset += l_text

        n_ref = struct.unpack("<i", buf[offset:offset+4])[0]
        offset += 4

        for _ in range(n_ref):
            while offset + 4 > len(buf):
                try: buf.extend(next(block_gen))
                except StopIteration: break

            l_name = struct.unpack("<i", buf[offset:offset+4])[0]
            offset += 4

            while offset + l_name + 4 > len(buf):
                try: buf.extend(next(block_gen))
                except StopIteration: break

            r_name = buf[offset:offset+l_name-1].decode("ascii", errors="replace")
            offset += l_name
            l_ref = struct.unpack("<i", buf[offset:offset+4])[0]
            offset += 4

            self.ref_names.append(r_name)
            self.ref_lengths.append(l_ref)

    def iter_alignments(self, max_reads: int = None) -> Generator[Dict[str, Any], None, None]:
        bgzf = BGZFStreamReader(self.bam_path)
        block_gen = bgzf.read_blocks()
        buf = bytearray()
        offset = 0
        reads_yielded = 0

        # Prime buffer and skip header
        while len(buf) < 65536:
            try: buf.extend(next(block_gen))
            except StopIteration: break

        offset = 4
        l_text = struct.unpack("<i", buf[offset:offset+4])[0]
        offset += 4 + l_text

        while len(buf) < offset + 4:
            try: buf.extend(next(block_gen))
            except StopIteration: break

        n_ref = struct.unpack("<i", buf[offset:offset+4])[0]
        offset += 4

        for _ in range(n_ref):
            while len(buf) < offset + 4:
                try: buf.extend(next(block_gen))
                except StopIteration: break
            l_name = struct.unpack("<i", buf[offset:offset+4])[0]
            offset += 4 + l_name + 4

        # Read alignments loop
        while True:
            if offset > 131072:
                buf = buf[offset:]
                offset = 0

            while len(buf) - offset < 36:
                try: buf.extend(next(block_gen))
                except StopIteration: break

            if len(buf) - offset < 36:
                break

            block_size = struct.unpack("<i", buf[offset:offset+4])[0]
            offset += 4

            while len(buf) - offset < block_size:
                try: buf.extend(next(block_gen))
                except StopIteration: break

            if len(buf) - offset < block_size:
                break

            record_bytes = buf[offset:offset+block_size]
            offset += block_size

            ref_id, pos, l_read_name, mapq, bin_id, n_cigar, flag, l_seq, next_ref, next_pos, tlen = struct.unpack(
                "<iiBBHHHIiii", record_bytes[:32]
            )

            # Skip unmapped reads
            if ref_id < 0 or pos < 0 or (flag & 4) != 0:
                continue

            r_chrom = self.ref_names[ref_id] if ref_id < len(self.ref_names) else f"ref_{ref_id}"

            c_offset = 32
            qname = record_bytes[c_offset:c_offset + l_read_name - 1].decode("ascii", errors="replace")
            c_offset += l_read_name

            cigar_parts = []
            for _ in range(n_cigar):
                val = struct.unpack("<I", record_bytes[c_offset:c_offset+4])[0]
                c_offset += 4
                op_len = val >> 4
                op_code = val & 0xF
                op_char = CIGAR_OPS[op_code] if op_code < len(CIGAR_OPS) else "M"
                cigar_parts.append(f"{op_len}{op_char}")
            cigar_str = "".join(cigar_parts) if cigar_parts else f"{l_seq}M"

            seq_bytes_len = (l_seq + 1) // 2
            seq_raw = record_bytes[c_offset:c_offset + seq_bytes_len]
            c_offset += seq_bytes_len

            seq_chars = []
            for b in seq_raw:
                seq_chars.append(DNA_BASES[b >> 4])
                if len(seq_chars) < l_seq:
                    seq_chars.append(DNA_BASES[b & 0xF])
            seq_str = "".join(seq_chars)

            qual_raw = record_bytes[c_offset:c_offset + l_seq]
            c_offset += l_seq
            qual_str = "".join(chr(33 + q) for q in qual_raw)

            yield {
                "qname": qname,
                "flag": flag,
                "chrom": r_chrom,
                "pos": pos,
                "mapq": mapq,
                "cigar": cigar_str,
                "seq": seq_str,
                "qual": qual_str,
                "read_len": l_seq
            }

            reads_yielded += 1
            if max_reads and reads_yielded >= max_reads:
                break
