import java.util.Random;

public class TestJavaVsPython {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestJavaVsPython(long seed) {
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

    public int randomIntBetween(int start, int end) {
        return start + nextInt(end - start + 1);
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

        System.out.println("=== TestJavaVsPython: seed = " + seed + " ===");

        TestJavaVsPython rng = new TestJavaVsPython(seed);
        System.out.println("Initial state: seed0=" + rng.seed0 + ", seed1=" + rng.seed1);

        for (int i = 0; i < 5; i++) {
            int result = rng.randomIntBetween(10, 15);
            System.out.println("Call " + (i+1) + ": " + result + ", state: seed0=" + rng.seed0 + ", seed1=" + rng.seed1);
        }

        System.out.println();
        System.out.println("=== Using java.util.Random directly ===");
        Random javaRng = new Random(seed);
        for (int i = 0; i < 5; i++) {
            int result = 10 + javaRng.nextInt(6);
            System.out.println("Call " + (i+1) + ": " + result);
        }
    }
}