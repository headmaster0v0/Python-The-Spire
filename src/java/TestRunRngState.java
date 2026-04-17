import java.util.Random;

public class TestRunRngState {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestRunRngState(long seed) {
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

    public int randomIntBetween(int start, int end) {
        return start + nextInt(end - start + 1);
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;  // floor_seed (seed + 1)

        System.out.println("=== Simulating RunRngState.generate_seeds(" + seed + ") ===");

        // Generate seeds like Python's RunRngState.generate_seeds does
        long monsterHpRngSeed0 = murmurHash3(seed);
        long monsterHpRngSeed1 = murmurHash3(monsterHpRngSeed0);

        System.out.println("monsterHpRng seeds:");
        System.out.println("  seed0 = " + monsterHpRngSeed0 + " (0x" + Long.toHexString(monsterHpRngSeed0) + ")");
        System.out.println("  seed1 = " + monsterHpRngSeed1 + " (0x" + Long.toHexString(monsterHpRngSeed1) + ")");

        TestRunRngState monsterHpRng = new TestRunRngState(seed);

        System.out.println("\n=== First 10 randomIntBetween(10, 15) on monsterHpRng ===");
        for (int i = 0; i < 10; i++) {
            int result = monsterHpRng.randomIntBetween(10, 15);
            System.out.println("  " + (i+1) + ": " + result);
        }

        System.out.println("\n=== Expected from Java log: [14, 6, 14, 5, 3, 3, ...] ===");
        System.out.println("HP should be at positions 0 and 2: 14, 14");
    }
}