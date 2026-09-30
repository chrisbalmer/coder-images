#!/usr/bin/env bash
# The validate job: the graph matches the tree, scripts parse, the pipelines lint and agree,
# and the tests pass. Runs offline.
#
# Usage: scripts/validate-ci.sh

set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

failed=0
run() {
    local label=$1
    shift
    if OUT=$("$@" 2>&1); then
        printf '  ok   %s\n' "$label"
    else
        printf '  FAIL %s\n' "$label"
        printf '%s\n' "$OUT" | sed 's/^/       /'
        failed=1
    fi
}

run "graph matches the tree" python3 scripts/ci-graph.py check
for script in scripts/*.sh; do
    run "bash -n $script" bash -n "$script"
done
run "python scripts parse" python3 -c \
    'import ast, sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]' scripts/*.py
if command -v actionlint > /dev/null; then
    run "actionlint" actionlint .github/workflows/publish.yml
else
    printf '  skip actionlint not installed\n'
fi
run "tests" python3 scripts/test_ci.py

if [ "$failed" -ne 0 ]; then
    echo "❌ validation failed"
    exit 1
fi
echo "✅ all checks passed"
