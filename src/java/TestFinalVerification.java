import java.util.Random;

public class TestFinalVerification {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestFinalVerification(long seed) {
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

    public int random(int start, int end) {
        return start + nextInt(end - start + 1);
    }

    public static void main(String[] args) {
        long floor1Seed = 5105399558371126245L;

        System.out.println("=== Java: Floor 1 seed " + floor1Seed + " ===");
        TestFinalVerification rng = new TestFinalVerification(floor1Seed);

        System.out.println("First 10 random(10, 15) calls:");
        for (int i = 0; i < 10; i++) {
            int result = rng.random(10, 15);
            System.out.println("  " + (i+1) + ": " + result);
        }

        System.out.println("\nSimulating LouseNormal (HP=10-15, bite=5-7):");
        TestFinalVerification rng2 = new TestFinalVerification(floor1Seed);
        for (int i = 0; i < 2; i++) {
            int hp = rng2.random(10, 15);
            int bite = rng2.random(5, 7);
            System.out.println("  Louse " + (i+1) + ": HP=" + hp + ", bite=" + bite);
        }
    }
}