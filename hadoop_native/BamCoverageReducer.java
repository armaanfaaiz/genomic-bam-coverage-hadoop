package org.genomics.hadoop;

import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

import java.io.IOException;

/**
 * Native Hadoop MapReduce Reducer for BAM coverage.
 * Aggregates position deltas and computes exact BedGraph depth records.
 */
public class BamCoverageReducer extends Reducer<Text, LongWritable, Text, NullWritable> {

    private final Text outText = new Text();
    private String currentChrom = null;
    private long currentPos = -1;
    private long currentDepth = 0;
    private long runStartPos = -1;

    @Override
    protected void reduce(Text key, Iterable<LongWritable> values, Context context)
            throws IOException, InterruptedException {
        String[] parts = key.toString().split("\t");
        String chrom = parts[0];
        long pos = Long.parseLong(parts[1]);

        long sumDelta = 0;
        for (LongWritable val : values) {
            sumDelta += val.get();
        }

        if (currentChrom != null && (!currentChrom.equals(chrom) || currentPos != pos)) {
            if (currentDepth > 0 && runStartPos != -1) {
                outText.set(currentChrom + "\t" + runStartPos + "\t" + currentPos + "\t" + currentDepth);
                context.write(outText, NullWritable.get());
            }
            if (!currentChrom.equals(chrom)) {
                currentDepth = 0;
            }
            runStartPos = pos;
        }

        currentChrom = chrom;
        currentPos = pos;
        currentDepth += sumDelta;
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
        if (currentChrom != null && currentDepth > 0 && runStartPos != -1) {
            outText.set(currentChrom + "\t" + runStartPos + "\t" + currentPos + "\t" + currentDepth);
            context.write(outText, NullWritable.get());
        }
    }
}
