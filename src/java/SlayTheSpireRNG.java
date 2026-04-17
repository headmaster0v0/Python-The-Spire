import java.util.Random;

public class SlayTheSpireRNG {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public SlayTheSpireRNG(long seed) {
        this.seed0 = murmurHash3(seed);
        this.seed1 = murmurHash3(this.seed0);
    }

    public SlayTheSpireRNG(long seed0, long seed1) {
        this.seed0 = seed0;
        this.seed1 = seed1;
    }

    private static long murmurHash3(long x) {
        x ^= x >>> 33;
        x *= MULT1;
        x ^= x >>> 33;
        x *= MULT2;
        x ^= x >>> 33;
        return x;
    }

    public long nextLong() {
        long s0y = this.seed0;
        long s1x = this.seed1;
        long result = s0y + s1x;
        long s1z = s0y ^ (s1x >>> 26);
        long s0yy = s1x + Long.rotateLeft(s0y, 13);
        this.seed0 = s0yy;
        this.seed1 = s1z;
        return result;
    }

    public int nextInt() {
        return (int) nextLong();
    }

    public int nextInt(int n) {
        if (n <= 0) {
            throw new IllegalArgumentException("n must be positive");
        }
        int bits;
        int value;
        do {
            bits = nextInt();
            value = bits % n;
        } while (bits - value + (n - 1) < 0);
        return value;
    }

    public int randomIntBetween(int start, int end) {
        return start + nextInt(end - start + 1);
    }

    public void setSeed0(long seed0) {
        this.seed0 = seed0;
    }

    public void setSeed1(long seed1) {
        this.seed1 = seed1;
    }

    public long getSeed0() {
        return this.seed0;
    }

    public long getSeed1() {
        return this.seed1;
    }

    public static void main(String[] args) {
        long seed = Long.parseLong(args[0]);
        int count = Integer.parseInt(args[1]);
        int start = Integer.parseInt(args[2]);
        int end = Integer.parseInt(args[3]);

        SlayTheSpireRNG rng = new SlayTheSpireRNG(seed);
        for (int i = 0; i < count; i++) {
            System.out.println(rng.randomIntBetween(start, end));
        }
    }
}
