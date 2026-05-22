import java.util.*;

public class WordFreqTest {
    private static int pass = 0;
    private static int fail = 0;

    private static void check(String name, boolean cond, String detail) {
        int n = pass + fail + 1;
        if (cond) {
            System.out.println("ok " + n + " - " + name);
            pass++;
        } else {
            System.out.println("not ok " + n + " - " + name + " # " + detail);
            fail++;
        }
    }

    public static void main(String[] args) {
        // 1. top-1 is the most frequent word
        WordFreq wf1 = new WordFreq();
        wf1.add("the cat sat on the mat the cat");
        // the:3  cat:2  sat:1  on:1  mat:1
        List<String> t1 = wf1.topK(1);
        check("top1 is 'the'",
              t1.size() == 1 && "the".equals(t1.get(0)),
              "got " + t1);

        // 2. top-2 in descending frequency order
        WordFreq wf2 = new WordFreq();
        wf2.add("a a a b b c");
        // a:3  b:2  c:1
        List<String> t2 = wf2.topK(2);
        check("top2[0] is 'a'",
              t2.size() >= 1 && "a".equals(t2.get(0)),
              "got " + t2);
        check("top2[1] is 'b'",
              t2.size() >= 2 && "b".equals(t2.get(1)),
              "got " + t2);

        // 3. k larger than vocabulary returns all words
        WordFreq wf3 = new WordFreq();
        wf3.add("hello world");
        check("topK(10) returns 2 words when vocab=2",
              wf3.topK(10).size() == 2,
              "got " + wf3.topK(10).size());

        // 4. multiple add() calls accumulate correctly
        WordFreq wf4 = new WordFreq();
        wf4.add("x x x y y z");
        wf4.add("x z z");
        // x:4  z:3  y:2
        List<String> t4 = wf4.topK(2);
        check("multi-add top2[0] is 'x'",
              t4.size() >= 1 && "x".equals(t4.get(0)),
              "got " + t4);
        check("multi-add top2[1] is 'z'",
              t4.size() >= 2 && "z".equals(t4.get(1)),
              "got " + t4);

        // 5. case-insensitive tokenisation
        WordFreq wf5 = new WordFreq();
        wf5.add("Apple apple APPLE");
        List<String> t5 = wf5.topK(1);
        check("case insensitive — top1 is 'apple'",
              t5.size() == 1 && "apple".equals(t5.get(0)),
              "got " + t5);

        // 6. non-alpha separators are treated as delimiters
        WordFreq wf6 = new WordFreq();
        wf6.add("one,two,one;two.one");
        // one:3  two:2
        List<String> t6 = wf6.topK(1);
        check("punctuation delimiters — top1 is 'one'",
              t6.size() == 1 && "one".equals(t6.get(0)),
              "got " + t6);

        System.out.println("1.." + (pass + fail));
        if (fail > 0) System.exit(1);
    }
}
