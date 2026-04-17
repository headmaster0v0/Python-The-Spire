import java.util.Random;

public class TestNextInt6 {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestNextInt6(long seed) {
        this.seed0 = murmurHash3(seed);
        this.seed1 = murmurHash3(this.seed0);
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
        long floor1Seed = 5105399558371126245L;

        System.out.println("=== Java nextInt(6) for floor 1 seed " + floor1Seed + " ===");
        TestNextInt6 rng = new TestNextInt6(floor1Seed);

        System.out.println("First 10 nextInt(6) values (raw, before adding start):");
        for (int i = 0; i < 10; i++) {
            int raw = rng.nextInt(6);
            System.out.println("  " + (i+1) + ": raw=" + raw + " -> with HP offset (10-15): " + (10 + raw));
        }
    }
}