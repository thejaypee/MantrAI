#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
CLI="$VENV_PYTHON -m mantrai.cli.main"

PASS=0
FAIL=0

test_case() {
    local name="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "PASS: $name"
        ((PASS++)) || true
    else
        echo "FAIL: $name"
        ((FAIL++)) || true
    fi
}

# Test 1: CLI read returns mantra
test_case "CLI read returns mantra" bash -c "$CLI read | grep -q 'Agent Mantra'"

# Test 2: CLI confirm logs to DB
test_case "CLI confirm logs to DB" bash -c "
    $CLI confirm --session-id bash-test-1 --context bash_ack
    $CLI log --session-id bash-test-1 --limit 5 | grep -q bash_ack
"

# Test 3: CLI check returns compliance status
test_case "CLI check returns status" bash -c "
    $CLI confirm --session-id bash-test-2
    $CLI check --session-id bash-test-2 | grep -q 'Session: bash-test-2'
"

# Test 4: CLI validate passes for valid file
test_case "CLI validate passes valid" bash -c "
    TMPFILE=\$(mktemp /tmp/mantra-XXXXXX.md)
    echo '## Agent Mantra — Follow This At All Times' > \"\$TMPFILE\"
    echo '' >> \"\$TMPFILE\"
    echo '> **VALID.**' >> \"\$TMPFILE\"
    echo '' >> \"\$TMPFILE\"
    echo '---' >> \"\$TMPFILE\"
    $CLI validate \"\$TMPFILE\"
    rm \"\$TMPFILE\"
"

# Test 5: CLI validate fails for invalid file
test_case "CLI validate fails invalid" bash -c "
    TMPFILE=\$(mktemp /tmp/mantra-XXXXXX.md)
    echo 'no header' > \"\$TMPFILE\"
    ! $CLI validate \"\$TMPFILE\"
    rm \"\$TMPFILE\"
"

# Test 6: MCP server starts and stays up
test_case "MCP server starts" bash -c "
    $VENV_PYTHON -m mantrai.mcp_server.server &
    PID=\$!
    sleep 1
    if kill -0 \$PID 2>/dev/null; then
        kill \$PID 2>/dev/null || true
        wait \$PID 2>/dev/null || true
    else
        exit 1
    fi
"

# Test 7: DB persists across CLI calls
test_case "DB persists across calls" bash -c "
    $CLI confirm --session-id bash-test-3 --context first
    $CLI confirm --session-id bash-test-3 --context second
    COUNT=\$($CLI log --session-id bash-test-3 --limit 10 | grep -c 'first\|second')
    [ \$COUNT -ge 2 ]
"

# Test 8: Inject forces mantra block
test_case "Inject returns mantra block" bash -c "
    $CLI inject --session-id bash-test-4 | grep -q 'MANTRA INJECTION REQUIRED'
"

# Test 9: Set level changes threshold
test_case "Set level changes behavior" bash -c "
    PYTHONPATH=\"$PROJECT_DIR\" $VENV_PYTHON -c '
from mantrai.mcp_server.server import mantrai_set_level
result = mantrai_set_level(\"bash-test-5\", \"strict\")
assert \"strict\" in result
result = mantrai_set_level(\"bash-test-5\", \"off\")
assert \"off\" in result
print(\"OK\")
'
"

# Test 10: Default mantra has at least 7 principles
test_case "Default mantra has 7+ principles" bash -c "
    $CLI read | grep -c '> \*\*' | awk '{exit \$1 < 7}'
"

echo ""
echo "========================================"
echo "Results: $PASS passed, $FAIL failed"
echo "========================================"

if [ $FAIL -gt 0 ]; then
    exit 1
fi
