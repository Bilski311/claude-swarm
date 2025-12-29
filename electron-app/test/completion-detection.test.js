/**
 * Test completion detection logic for wait_for_workers
 *
 * A worker is "done" when its output shows the Claude Code prompt:
 * - Line starting with "> "
 * - Or "? for shortcuts"
 */

const assert = require('assert');

// Strip ANSI escape codes (same as in conductor_server.py)
function stripAnsi(text) {
  return text.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, '');
}

// Check if worker is done (logic from wait_for_workers)
function isWorkerDone(output) {
  const lines = stripAnsi(output).trim().split('\n');
  if (!lines.length) return false;

  const lastLines = lines.slice(-5);  // Check last 5 lines
  for (const line of lastLines) {
    const cleanLine = line.trim();
    if (cleanLine.startsWith('> ') || cleanLine === '>' || cleanLine.includes('? for shortcuts')) {
      return true;
    }
  }
  return false;
}

// Test cases
function runTests() {
  console.log('Running completion detection tests...\n');

  let passed = 0;
  let failed = 0;

  // Test 1: Empty output - not done
  try {
    assert.strictEqual(isWorkerDone(''), false);
    console.log('✓ Test 1: Empty output is not done');
    passed++;
  } catch (e) {
    console.log('✗ Test 1 FAILED:', e.message);
    failed++;
  }

  // Test 2: Output with prompt "> " at end - done
  try {
    const output = `Some task output here
Doing work...
Done with task.

> `;
    assert.strictEqual(isWorkerDone(output), true);
    console.log('✓ Test 2: Output with "> " prompt is done');
    passed++;
  } catch (e) {
    console.log('✗ Test 2 FAILED:', e.message);
    failed++;
  }

  // Test 3: Output with "? for shortcuts" - done
  try {
    const output = `Task complete.
Summary of findings...

>
  ? for shortcuts`;
    assert.strictEqual(isWorkerDone(output), true);
    console.log('✓ Test 3: Output with "? for shortcuts" is done');
    passed++;
  } catch (e) {
    console.log('✗ Test 3 FAILED:', e.message);
    failed++;
  }

  // Test 4: Output still working (no prompt) - not done
  try {
    const output = `Starting task...
Reading files...
Analyzing code...
Still processing...`;
    assert.strictEqual(isWorkerDone(output), false);
    console.log('✓ Test 4: Output without prompt is not done');
    passed++;
  } catch (e) {
    console.log('✗ Test 4 FAILED:', e.message);
    failed++;
  }

  // Test 5: Output with ANSI codes - should still detect prompt
  try {
    const output = `\x1b[32mTask complete\x1b[0m
\x1b[1m> \x1b[0m`;
    assert.strictEqual(isWorkerDone(output), true);
    console.log('✓ Test 5: Output with ANSI codes still detects prompt');
    passed++;
  } catch (e) {
    console.log('✗ Test 5 FAILED:', e.message);
    failed++;
  }

  // Test 6: Prompt with text after it - done (user typing)
  try {
    const output = `Research complete.

> Add a new feature`;
    assert.strictEqual(isWorkerDone(output), true);
    console.log('✓ Test 6: Prompt with text after is done');
    passed++;
  } catch (e) {
    console.log('✗ Test 6 FAILED:', e.message);
    failed++;
  }

  // Test 7: Claude thinking indicator - not done
  try {
    const output = `Starting analysis...
● Thinking...`;
    assert.strictEqual(isWorkerDone(output), false);
    console.log('✓ Test 7: Thinking indicator is not done');
    passed++;
  } catch (e) {
    console.log('✗ Test 7 FAILED:', e.message);
    failed++;
  }

  // Test 8: Real Claude Code output format
  try {
    const output = `● Here's my analysis of the codebase:

## Architecture Overview
- Component-based structure
- Event-driven communication

The system is well-organized.

>
  ? for shortcuts`;
    assert.strictEqual(isWorkerDone(output), true);
    console.log('✓ Test 8: Real Claude Code output format detected');
    passed++;
  } catch (e) {
    console.log('✗ Test 8 FAILED:', e.message);
    failed++;
  }

  console.log(`\n${passed} passed, ${failed} failed`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
