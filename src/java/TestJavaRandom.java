import java.util.Random;

public class TestJavaRandom {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestJavaRandom(long seed) {
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
        TestJavaRandom rng = new TestJavaRandom(seed);

        System.out.println("=== Fresh start ===");
        System.out.println("seed0 = " + rng.seed0 + " (0x" + Long.toHexString(rng.seed0) + ")");
        System.out.println("seed1 = " + rng.seed1 + " (0x" + Long.toHexString(rng.seed1) + ")");

        System.out.println("\n=== First randomIntBetween(10, 15) call ===");
        int result1 = rng.randomIntBetween(10, 15);
        System.out.println("Result: " + result1);

        System.out.println("\n=== Second randomIntBetween(10, 15) call ===");
        int result2 = rng.randomIntBetween(10, 15);
        System.out.println("Result: " + result2);

        System.out.println("\n=== Third randomIntBetween(10, 15) call ===");
        int result3 = rng.randomIntBetween(10, 15);
        System.out.println("Result: " + result3);

        System.out.println("\n=== Ten randomIntBetween(10, 15) calls ===");
        TestJavaRandom rng2 = new TestJavaRandom(seed);
        for (int i = 0; i < 10; i++) {
            System.out.println("  " + (i+1) + ": " + rng2.randomIntBetween(10, 15));
        }
    }
}
