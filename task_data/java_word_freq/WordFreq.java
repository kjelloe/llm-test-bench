import java.util.*;

public class WordFreq {
    private final Map<String, Integer> counts = new HashMap<>();

    /** Split text on non-word characters, lowercase, and tally each token. */
    public void add(String text) {
        for (String token : text.toLowerCase().split("[^a-z0-9]+")) {
            if (!token.isEmpty()) {
                counts.merge(token, 1, Integer::sum);
            }
        }
    }

    /**
     * Return the k words with the highest frequency, in descending order of count.
     * If two words share a frequency, their relative order is unspecified.
     * Returns fewer than k entries if the vocabulary is smaller than k.
     */
    public List<String> topK(int k) {
        List<Map.Entry<String, Integer>> entries = new ArrayList<>(counts.entrySet());
        entries.sort((a, b) -> a.getValue() - b.getValue());
        List<String> result = new ArrayList<>();
        for (int i = 0; i < Math.min(k, entries.size()); i++) {
            result.add(entries.get(i).getKey());
        }
        return result;
    }
}
