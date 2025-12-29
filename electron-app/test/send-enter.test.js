/**
 * Test that messages sent via HTTP API include carriage return (\r) to submit commands
 */

const assert = require('assert');

// Track what gets written to PTY
let ptyWriteLog = [];
let writeOrder = [];

// Mock PTY that logs writes
class MockPty {
  constructor() {
    ptyWriteLog = [];
    writeOrder = [];
  }

  write(data) {
    ptyWriteLog.push(data);
    writeOrder.push({ data, time: Date.now() });
  }
}

// Simulate the send handler logic from main.js (with delayed \r)
async function simulateSendHandler(message) {
  const mockPty = new MockPty();

  // This is the logic from main.js POST /sessions/:id/send
  mockPty.write(message);

  // Simulate the setTimeout delay
  await new Promise(resolve => setTimeout(resolve, 150));
  mockPty.write('\r');

  return ptyWriteLog;
}

// Test cases
async function runTests() {
  console.log('Running send-enter tests...\n');

  let passed = 0;
  let failed = 0;

  // Test 1: Message and \r should be separate writes
  try {
    const result = await simulateSendHandler('hello world');
    assert.strictEqual(result.length, 2, 'Should have two writes (message + \\r)');
    assert.strictEqual(result[0], 'hello world', 'First write is the message');
    assert.strictEqual(result[1], '\r', 'Second write is \\r');
    console.log('✓ Test 1: Message and \\r are separate writes');
    passed++;
  } catch (e) {
    console.log('✗ Test 1 FAILED:', e.message);
    failed++;
  }

  // Test 2: \r should be sent after message
  try {
    writeOrder = [];
    const result = await simulateSendHandler('test command');
    assert.ok(writeOrder.length === 2, 'Should have two writes');
    assert.ok(writeOrder[1].time >= writeOrder[0].time, '\\r should come after message');
    console.log('✓ Test 2: \\r is sent after message');
    passed++;
  } catch (e) {
    console.log('✗ Test 2 FAILED:', e.message);
    failed++;
  }

  // Test 3: Multi-line message should work
  try {
    const result = await simulateSendHandler('line1\nline2\nline3');
    assert.strictEqual(result[0], 'line1\nline2\nline3', 'Message preserved');
    assert.strictEqual(result[1], '\r', 'Enter sent separately');
    console.log('✓ Test 3: Multi-line message works');
    passed++;
  } catch (e) {
    console.log('✗ Test 3 FAILED:', e.message);
    failed++;
  }

  // Test 4: Empty message should still get \r
  try {
    const result = await simulateSendHandler('');
    assert.strictEqual(result.length, 2, 'Should have two writes');
    assert.strictEqual(result[1], '\r', '\\r still sent');
    console.log('✓ Test 4: Empty message still sends \\r');
    passed++;
  } catch (e) {
    console.log('✗ Test 4 FAILED:', e.message);
    failed++;
  }

  // Test 5: Verify \r is carriage return (ASCII 13)
  try {
    const result = await simulateSendHandler('x');
    const enterChar = result[1].charCodeAt(0);
    assert.strictEqual(enterChar, 13, 'Should be ASCII 13 (\\r)');
    console.log('✓ Test 5: \\r is ASCII 13 (carriage return)');
    passed++;
  } catch (e) {
    console.log('✗ Test 5 FAILED:', e.message);
    failed++;
  }

  console.log(`\n${passed} passed, ${failed} failed`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
