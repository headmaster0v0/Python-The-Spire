import java.util.Random;

public class TestDebug {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestDebug(long seed) {
        this.seed0 = murmurHash3(seed == 0L ? Long.MIN_VALUE : seed);
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
        long s0;
        long s1 = this.seed0;
        this.seed0 = s0 = this.seed1;
        s1 ^= s1 << 23;
        this.seed1 = s1 ^ s0 ^ s1 >>> 17 ^ s0 >>> 26;
        return this.seed1 + s0;
    }

    public int nextInt(int n) {
        if (n <= 0) throw new IllegalArgumentException();
        long bits = nextLong() >>> 1;
        System.out.println("  nextInt(" + n + "): bits=" + bits + " (0x" + Long.toHexString(bits) + ")");
        long val = bits % n;
        System.out.println("  val = bits % " + n + " = " + val);
        if (bits - val + (n - 1) < 0) {
            do {
                bits = nextLong() >>> 1;
                val = bits % n;
            } while (bits - val + (n - 1) < 0);
        }
        return (int) val;
    }

    public int randomIntBetween(int start, int end) {
        return start + nextInt(end - start + 1);
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;

        System.out.println("=== TestDebug: seed = " + seed + " ===");

        TestDebug rng = new TestDebug(seed);
        System.out.println("Initial state: seed0=" + rng.seed0 + ", seed1=" + rng.seed1);

        System.out.println("\n=== First randomIntBetween(10, 15) ===");
        int result = rng.randomIntBetween(10, 15);
        System.out.println("Result: " + result);

        System.out.println("\n=== Second randomIntBetween(10, 15) ===");
        result = rng.randomIntBetween(10, 15);
        System.out.println("Result: " + result);
    }
}