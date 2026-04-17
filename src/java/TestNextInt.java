import java.util.Random;

public class TestNextInt {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private long seed0;
    private long seed1;

    public TestNextInt(long seed) {
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

    public int randomIntBetween(int start, int end) {
        int n = end - start + 1;
        int bits, value;
        do {
            bits = nextInt();
            value = bits % n;
        } while (bits - value + (n - 1) < 0);
        return start + value;
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;
        TestNextInt rng = new TestNextInt(seed);
        System.out.println("seed0 = " + rng.seed0 + " (0x" + Long.toHexString(rng.seed0) + ")");
        System.out.println("seed1 = " + rng.seed1 + " (0x" + Long.toHexString(rng.seed1) + ")");
        System.out.println();
        System.out.println("nextInt outputs:");
        for (int i = 0; i < 10; i++) {
            long nl = rng.nextLong();
            int ni = (int) nl;
            System.out.println("  nextLong " + (i+1) + ": " + nl + " (0x" + Long.toHexString(nl) + ")");
            System.out.println("  nextInt " + (i+1) + ": " + ni + " (0x" + Integer.toHexString(ni) + ")");
        }
        System.out.println();
        System.out.println("randomIntBetween(10, 15) outputs:");
        for (int i = 0; i < 10; i++) {
            System.out.println("  " + (i+1) + ": " + rng.randomIntBetween(10, 15));
        }
    }
}
