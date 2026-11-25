package org.genomics.hadoop;

import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

import java.io.IOException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Native Hadoop MapReduce Mapper for BAM/SAM alignment coverage.
 * Emits intermediate key-values: (chrom:pos, depth_diff).
 * Inspired by Samaddar et al. (2019) and PanDepth (Yu & Shi, 2024).
 */
public class BamCoverageMapper extends Mapper<LongWritable, Text, Text, LongWritable> {

    private final Text outKey = new Text();
    private final LongWritable outVal = new LongWritable();
    private final Pattern cigarPattern = Pattern.compile("(\\d+)([MIDNSHP=X])");

    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.startsWith("@") || line.trim().isEmpty()) {
            return;
        }

        String[] fields = line.split("\t");
        if (fields.length < 11) {
            return;
        }

        int flag = Integer.parseInt(fields[1]);
        // Filter unmapped (0x4), secondary (0x100), qc-fail (0x200), duplicate (0x400)
        if ((flag & 0xF04) != 0) {
            return;
        }

        String chrom = fields[2];
        long pos = Long.parseLong(fields[3]);
        String cigar = fields[5];

        // Parse CIGAR to find mapped intervals and emit boundary differences
        Matcher matcher = cigarPattern.matcher(cigar);
        long currPos = pos;

        while (matcher.find()) {
            int len = Integer.parseInt(matcher.group(1));
            String op = matcher.group(2);

            if (op.equals("M") || op.equals("=") || op.equals("X")) {
                long startPos = currPos;
                long endPos = currPos + len;

                // Emit +1 at start of alignment
                outKey.set(chrom + "\t" + startPos);
                outVal.set(1L);
                context.write(outKey, outVal);

                // Emit -1 at end of alignment
                outKey.set(chrom + "\t" + endPos);
                outVal.set(-1L);
                context.write(outKey, outVal);

                currPos += len;
            } else if (op.equals("D") || op.equals("N")) {
                currPos += len;
            }
        }
    }
}
