import java.util.Random;

public class TestJavaUtilRandom {
    public static void main(String[] args) {
        // Java game uses: monsterHpRng = new Random(Settings.seed + currFloor)
        long seed = 5105399558371126244L + 1;  // seed + floor
        Random rng = new Random(seed);

        System.out.println("=== java.util.Random with seed = " + seed + " ===");

        for (int i = 0; i < 6; i++) {
            // game calls randomIntBetween(10, 15), which is 10 + nextInt(6)
            int result = 10 + rng.nextInt(6);
            System.out.println("Call " + (i+1) + ": " + result);
        }
    }
}