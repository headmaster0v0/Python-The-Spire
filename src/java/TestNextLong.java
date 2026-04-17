import java.util.Random;

public class TestNextLong {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestNextLong(long seed) {
        this.seed0 = murmurHash3(seed);
        this.seed1 = murmurHash3(this.seed0);
        System.out.println("seed0 = " + seed0 + " (0x" + Long.toHexString(seed0) + ")");
        System.out.println("seed1 = " + seed1 + " (0x" + Long.toHexString(seed1) + ")");
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
        long s0 = this.seed0;
        long s1 = this.seed1;
        long result = s0 + s1;
        s1 ^= s1 << 23;
        this.seed1 = s1 ^ s0 ^ s1 >>> 17 ^ s0 >>> 26;
        this.seed0 = s0;
        return result;
    }

    public int nextInt() {
        return (int) nextLong();
    }

    public int nextInt(int n) {
        if (n <= 0) throw new IllegalArgumentException();
        int bits = nextInt();
        int val = bits % n;
        if (bits - val + (n - 1) < 0) {
            do {
                bits = nextInt();
                val = bits % n;
            } while (bits - val + (n - 1) < 0);
        }
        return val;
    }

    public int randomIntBetween(int start, int end) {
        return start + nextInt(end - start + 1);
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;

        System.out.println("=== Test with seed " + seed + " ===");
        TestNextLong rng = new TestNextLong(seed);

        System.out.println("\n=== First 5 nextLong() values ===");
        for (int i = 0; i < 5; i++) {
            long val = rng.nextLong();
            System.out.println("  " + (i+1) + ": " + val + " (0x" + Long.toHexString(val) + ")");
        }
    }
}