import java.util.Random;

public class TestFloor1Seed {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestFloor1Seed(long seed) {
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
        long seed = 5105399558371126245L;  // Floor 1 seed (seed + 1)

        System.out.println("=== Java TestFloor1Seed with seed " + seed + " ===");
        TestFloor1Seed rng = new TestFloor1Seed(seed);

        System.out.println("\n=== First 10 randomIntBetween(10, 15) ===");
        for (int i = 0; i < 10; i++) {
            int result = rng.randomIntBetween(10, 15);
            System.out.println("  " + (i+1) + ": " + result);
        }

        System.out.println("\n=== Simulate LouseNormal HP calls (ascension=0, range 10-15) ===");
        TestFloor1Seed rng2 = new TestFloor1Seed(seed);
        for (int i = 0; i < 5; i++) {
            int hp = rng2.randomIntBetween(10, 15);
            int bite = rng2.randomIntBetween(5, 7);
            System.out.println("  Louse " + (i+1) + ": hp=" + hp + ", bite=" + bite);
        }
    }
}