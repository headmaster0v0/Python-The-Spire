import java.util.Random;

public class TestMurmur {
    private static final long MULT1 = -49064778989728563L;
    private static final long MULT2 = -4265267296055464877L;

    private static long murmurHash3(long x) {
        x ^= x >>> 33;
        x *= MULT1;
        x ^= x >>> 33;
        x *= MULT2;
        x ^= x >>> 33;
        return x;
    }

    public static void main(String[] args) {
        long seed = 5105399558371126245L;
        long seed0 = murmurHash3(seed);
        long seed1 = murmurHash3(seed0);
        System.out.println("seed0 = " + seed0 + " (0x" + Long.toHexString(seed0) + ")");
        System.out.println("seed1 = " + seed1 + " (0x" + Long.toHexString(seed1) + ")");
    }
}
