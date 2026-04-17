import java.util.Random;

public class TestNextLong2 {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestNextLong2(long seed) {
        this.seed0 = murmurHash3(seed);
        this.seed1 = murmurHash3(this.seed0);
        System.out.println("Initial state:");
        System.out.println("  seed0 = " + seed0 + " (0x" + Long.toHexString(seed0) + ")");
        System.out.println("  seed1 = " + seed1 + " (0x" + Long.toHexString(seed1) + ")");
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
        System.out.println("  Before nextLong: s0=0x" + Long.toHexString(s0) + ", s1=0x" + Long.toHexString(s1));
        System.out.println("  result = s0 + s1 = 0x" + Long.toHexString(result));
        s1 ^= s1 << 23;
        System.out.println("  After s1 ^= s1 << 23: s1 = 0x" + Long.toHexString(s1));
        this.seed1 = s1 ^ s0 ^ s1 >>> 17 ^ s0 >>> 26;
        System.out.println("  new seed1 = s1 ^ s0 ^ s1>>>17 ^ s0>>>26 = 0x" + Long.toHexString(this.seed1));
        this.seed0 = s0;
        System.out.println("  new seed0 = 0x" + Long.toHexString(this.seed0));
        return result;
    }

    public int nextInt(int n) {
        if (n <= 0) throw new IllegalArgumentException();
        long bits = nextLong() >>> 1;
        long val = bits % n;
        if (bits - val + (n - 1) < 0) {
            do {
                bits = nextLong() >>> 1;
                val = bits % n;
            } while (bits - val + (n - 1) < 0);
        }
        return (int) val;
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;
        System.out.println("=== Java TestNextLong2 ===");
        System.out.println("seed = " + seed + " (0x" + Long.toHexString(seed) + ")");
        TestNextLong2 rng = new TestNextLong2(seed);

        System.out.println("\n=== First few nextLong() calls ===");
        for (int i = 0; i < 3; i++) {
            System.out.println("\nCall " + (i+1) + ":");
            long val = rng.nextLong();
            System.out.println("  returned: " + val + " (0x" + Long.toHexString(val) + ")");
        }

        System.out.println("\n=== First few nextInt(6) calls ===");
        TestNextLong2 rng2 = new TestNextLong2(seed);
        for (int i = 0; i < 3; i++) {
            System.out.println("\nCall " + (i+1) + ":");
            int val = rng2.nextInt(6);
            System.out.println("  returned: " + val);
        }
    }
}