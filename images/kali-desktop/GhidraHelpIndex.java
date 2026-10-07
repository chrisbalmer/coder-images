// Rebuilds the help search indexes that Kali's ghidra package ships empty, then proves the help
// window can merge every module's search view.
//
// Upstream's build runs JavaHelp's indexer into help/<Module>_JavaHelpSearch/ in each module jar
// and names that index in the module's help set. Kali's package has the directories but no index
// files, and help sets without the index, so JavaHelp's MergingSearchEngine.merge throws
// "IllegalArgumentException: view is invalid" whenever the help window opens (What's New on
// first launch, Help > Contents, F1). This runs the indexer that ships in the package
// (javahelp-2.0.05.jar) over each module's own help pages, the way upstream's indexHelp task
// does, and leaves any module that already has an index alone, so a fixed package makes it a
// no-op.
//
// Usage (one JVM, so it stays quick under emulation):
//   java -cp <javahelp jar> GhidraHelpIndex.java <ghidra install dir>          repair, then check
//   java -cp <javahelp jar> GhidraHelpIndex.java --check <ghidra install dir>  check only

import com.sun.java.help.search.Indexer;
import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermission;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import javax.help.HelpSet;
import javax.help.NavigatorView;
import javax.help.search.MergingSearchEngine;
import javax.help.search.SearchEvent;
import javax.help.search.SearchListener;
import javax.help.search.SearchQuery;

public class GhidraHelpIndex {
    static final List<String> INDEX_FILES = List.of("DOCS", "DOCS.TAB", "OFFSETS", "POSITIONS", "SCHEMA", "TMAP");
    static final String SEARCH_TYPE = "<type>help.CustomSearchView</type>";
    static final URL JAVAHELP = Indexer.class.getProtectionDomain().getCodeSource().getLocation();

    public static void main(String[] args) throws Exception {
        boolean checkOnly = args.length == 2 && args[0].equals("--check");
        Path install = Path.of(args[args.length - 1]);
        List<Path> jars;
        try (Stream<Path> s = Files.walk(install.resolve("Ghidra"))) {
            jars = s.filter(p -> p.getFileName().toString().endsWith(".jar")
                    && p.getParent().getFileName().toString().equals("lib")).sorted().toList();
        }
        if (!checkOnly) {
            int fixed = 0;
            for (Path jar : jars) {
                // Rewriting a jar replaces the file; keep its mode, so the coder user can read it.
                Set<PosixFilePermission> mode = Files.getPosixFilePermissions(jar);
                if (repair(jar)) {
                    Files.setPosixFilePermissions(jar, mode);
                    fixed++;
                }
            }
            System.out.println("ghidra-help-index: indexed " + fixed + " module(s)");
        }
        check(jars);
    }

    // Index one module jar if its help set has a search view but no index. Returns true if changed.
    static boolean repair(Path jar) throws Exception {
        try (FileSystem fs = FileSystems.newFileSystem(jar)) {
            Path help = fs.getPath("/help");
            if (!Files.isDirectory(help)) return false;
            boolean changed = false;
            for (Path hs : list(help, "*_HelpSet.hs")) {
                String module = hs.getFileName().toString().replaceFirst("_HelpSet\\.hs$", "");
                Path db = help.resolve(module + "_JavaHelpSearch");
                String text = Files.readString(hs, StandardCharsets.ISO_8859_1);
                if (!Files.isDirectory(db) || !text.contains(SEARCH_TYPE) || text.contains("<data engine=")) continue;

                Path work = Files.createTempDirectory("ghidra-help-");
                try {
                    Path root = work.resolve("help");
                    List<String> pages = new ArrayList<>();
                    try (Stream<Path> s = Files.walk(help)) {
                        for (Path p : s.filter(Files::isRegularFile).toList()) {
                            String name = p.getFileName().toString();
                            if (!name.endsWith(".htm") && !name.endsWith(".html")) continue;
                            Path out = root.resolve(help.relativize(p).toString());
                            Files.createDirectories(out.getParent());
                            Files.copy(p, out);
                            pages.add(out.toString());
                        }
                    }
                    if (pages.isEmpty()) continue;
                    // Same arguments as upstream's indexHelp task: strip the help root so the
                    // index names pages relative to the help set.
                    Path config = work.resolve("helpconfig");
                    Files.writeString(config, "IndexRemove " + root + "/\n");
                    Path out = work.resolve("db");
                    List<String> argv = new ArrayList<>(List.of("-c", config.toString(), "-db", out.toString()));
                    argv.addAll(pages);
                    // The indexer keeps static state that breaks a second run in one class
                    // loader, so each module gets a fresh one.
                    try (URLClassLoader isolated = new URLClassLoader(new URL[] {JAVAHELP},
                            ClassLoader.getPlatformClassLoader())) {
                        Object indexer = isolated.loadClass(Indexer.class.getName())
                                .getConstructor().newInstance();
                        indexer.getClass().getMethod("compile", String[].class)
                                .invoke(indexer, (Object) argv.toArray(String[]::new));
                    }
                    for (String f : INDEX_FILES) {
                        if (!Files.isRegularFile(out.resolve(f)))
                            throw new IOException(jar + ": the indexer wrote no " + f);
                        Files.copy(out.resolve(f), db.resolve(f), StandardCopyOption.REPLACE_EXISTING);
                    }
                } finally {
                    try (Stream<Path> s = Files.walk(work)) {
                        s.sorted(Comparator.reverseOrder()).forEach(p -> p.toFile().delete());
                    }
                }
                String data = SEARCH_TYPE + "\n\t\t<data engine=\"com.sun.java.help.search.DefaultSearchEngine\">"
                        + module + "_JavaHelpSearch</data>";
                Files.writeString(hs, text.replace(SEARCH_TYPE, data), StandardCharsets.ISO_8859_1);
                System.out.println("ghidra-help-index: " + module + " (" + jar.getFileName() + ")");
                changed = true;
            }
            return changed;
        }
    }

    // Merge every module's search view, as JavaHelp does when the help window first opens.
    static void check(List<Path> jars) throws Exception {
        URL[] urls = new URL[jars.size()];
        for (int i = 0; i < urls.length; i++) urls[i] = jars.get(i).toUri().toURL();
        ClassLoader loader = new URLClassLoader(urls, GhidraHelpIndex.class.getClassLoader());
        MergingSearchEngine engine = null;
        int views = 0;
        List<String> bad = new ArrayList<>();
        for (Path jar : jars) {
            try (FileSystem fs = FileSystems.newFileSystem(jar)) {
                Path help = fs.getPath("/help");
                if (!Files.isDirectory(help)) continue;
                for (Path hs : list(help, "*_HelpSet.hs")) {
                    URL url = URI.create("jar:" + jar.toUri() + "!" + hs).toURL();
                    NavigatorView view = new HelpSet(loader, url).getNavigatorView("Search");
                    if (view == null) continue;
                    views++;
                    try {
                        // merge() rejects a view with no index; the constructor does not.
                        if (engine == null) engine = new MergingSearchEngine(view);
                        engine.merge(view);
                    } catch (IllegalArgumentException e) {
                        bad.add(jar.getFileName() + ": " + e.getMessage());
                    }
                }
            }
        }
        System.out.println("ghidra-help-index: " + views + " search views, " + bad.size() + " unusable");
        bad.forEach(b -> System.out.println("  " + b));
        if (views == 0 || !bad.isEmpty()) System.exit(1);

        // And the merged index answers a query, as the help window's Search tab would.
        int[] hits = {0};
        CountDownLatch done = new CountDownLatch(1);
        SearchQuery query = engine.createQuery();
        query.addSearchListener(new SearchListener() {
            public void itemsFound(SearchEvent e) {
                for (Enumeration<?> i = e.getSearchItems(); i.hasMoreElements(); i.nextElement()) hits[0]++;
            }
            public void searchStarted(SearchEvent e) {}
            public void searchFinished(SearchEvent e) { done.countDown(); }
        });
        query.start("memory", Locale.ENGLISH);
        if (!done.await(120, TimeUnit.SECONDS) || hits[0] == 0) {
            System.out.println("ghidra-help-index: a search for \"memory\" found nothing");
            System.exit(1);
        }
        System.out.println("ghidra-help-index: a search for \"memory\" found " + hits[0] + " topics");
    }

    static List<Path> list(Path dir, String glob) throws IOException {
        List<Path> out = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, glob)) { ds.forEach(out::add); }
        return out;
    }
}
