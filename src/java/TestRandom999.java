import java.util.Random;

public class TestRandom999 {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestRandom999(long seed) {
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

    public int random999() {
        return nextInt(1000);
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;

        System.out.println("=== Java: First 10 random(999) ===");
        TestRandom999 rng = new TestRandom999(seed);
        for (int i = 0; i < 10; i++) {
            System.out.println("  " + (i+1) + ": " + rng.random999());
        }

        System.out.println("\n=== Java: Then 10 randomIntBetween(10, 15) ===");
        for (int i = 0; i < 10; i++) {
            int bits = rng.nextInt();
            int val = bits % 6;
            System.out.println("  " + (i+1) + ": bits=" + bits + ", val=" + val);
        }

        System.out.println("\n=== Java: Fresh start randomIntBetween(10, 15) ===");
        TestRandom999 rng2 = new TestRandom999(seed);
        for (int i = 0; i < 10; i++) {
            int bits = rng2.nextInt();
            int n = 6;
            int val = bits % n;
            int diff = bits - val + (n - 1);
            boolean accept = diff >= 0;
            int result = accept ? val : (val < 0 ? val + n : val);
            System.out.println("  " + (i+1) + ": bits=" + bits + ", val=" + val + ", diff=" + diff + ", accept=" + accept + ", result=" + (10 + result));
        }
    }
}