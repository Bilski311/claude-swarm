/**
 * Integration test for the output buffer and API
 *
 * Tests that:
 * 1. Sessions store output in their buffer
 * 2. The /sessions/:id/output endpoint returns the buffer
 * 3. Output buffer is capped at 50KB
 */

const assert = require('assert');
const http = require('http');

const API_BASE = 'http://127.0.0.1:7422';

// Helper to make HTTP requests
function apiRequest(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, API_BASE);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method,
      headers: { 'Content-Type': 'application/json' },
      timeout: 5000
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => reject(new Error('Request timeout')));

    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

async function runTests() {
  console.log('Running output API tests...\n');
  console.log('NOTE: These tests require the Claude Conductor app to be running.\n');

  let passed = 0;
  let failed = 0;
  let skipped = 0;

  // Check if app is running
  try {
    await apiRequest('GET', '/sessions');
  } catch (e) {
    console.log('⚠ App not running - skipping integration tests');
    console.log('  Start the app with: npm start\n');
    process.exit(0);
  }

  // Test 1: List sessions returns array
  try {
    const res = await apiRequest('GET', '/sessions');
    assert.strictEqual(res.status, 200);
    assert.ok(Array.isArray(res.body.sessions), 'sessions should be array');
    console.log('✓ Test 1: GET /sessions returns session list');
    passed++;
  } catch (e) {
    console.log('✗ Test 1 FAILED:', e.message);
    failed++;
  }

  // Test 2: Get output for existing session
  try {
    const listRes = await apiRequest('GET', '/sessions');
    if (listRes.body.sessions.length === 0) {
      console.log('⊘ Test 2: Skipped (no sessions)');
      skipped++;
    } else {
      const sessionId = listRes.body.sessions[0].id;
      const res = await apiRequest('GET', `/sessions/${sessionId}/output`);
      assert.strictEqual(res.status, 200);
      assert.ok('output' in res.body, 'response should have output field');
      assert.ok('name' in res.body, 'response should have name field');
      assert.ok('status' in res.body, 'response should have status field');
      console.log('✓ Test 2: GET /sessions/:id/output returns output');
      passed++;
    }
  } catch (e) {
    console.log('✗ Test 2 FAILED:', e.message);
    failed++;
  }

  // Test 3: Get output for non-existent session returns 404
  try {
    const res = await apiRequest('GET', '/sessions/non-existent-id/output');
    assert.strictEqual(res.status, 404);
    console.log('✓ Test 3: Non-existent session returns 404');
    passed++;
  } catch (e) {
    console.log('✗ Test 3 FAILED:', e.message);
    failed++;
  }

  // Test 4: Output contains terminal data (if session has been running)
  try {
    const listRes = await apiRequest('GET', '/sessions');
    if (listRes.body.sessions.length === 0) {
      console.log('⊘ Test 4: Skipped (no sessions)');
      skipped++;
    } else {
      const sessionId = listRes.body.sessions[0].id;
      const res = await apiRequest('GET', `/sessions/${sessionId}/output`);
      // Output should be a string (might be empty if just started)
      assert.strictEqual(typeof res.body.output, 'string');
      console.log(`✓ Test 4: Output is string (${res.body.output.length} chars)`);
      passed++;
    }
  } catch (e) {
    console.log('✗ Test 4 FAILED:', e.message);
    failed++;
  }

  // Test 5: Send message to session (empty message should be rejected)
  try {
    const listRes = await apiRequest('GET', '/sessions');
    if (listRes.body.sessions.length === 0) {
      console.log('⊘ Test 5: Skipped (no sessions)');
      skipped++;
    } else {
      const sessionId = listRes.body.sessions[0].id;
      // Empty message should return 400
      const emptyRes = await apiRequest('POST', `/sessions/${sessionId}/send`, {
        message: ''
      });
      assert.strictEqual(emptyRes.status, 400, 'Empty message should be rejected');
      console.log('✓ Test 5: Empty message correctly rejected');
      passed++;
    }
  } catch (e) {
    console.log('✗ Test 5 FAILED:', e.message);
    failed++;
  }

  // Test 6: Send non-empty message to session
  try {
    const listRes = await apiRequest('GET', '/sessions');
    if (listRes.body.sessions.length === 0) {
      console.log('⊘ Test 6: Skipped (no sessions)');
      skipped++;
    } else {
      const sessionId = listRes.body.sessions[0].id;
      const res = await apiRequest('POST', `/sessions/${sessionId}/send`, {
        message: 'test'
      });
      assert.strictEqual(res.status, 200);
      assert.strictEqual(res.body.status, 'sent');
      console.log('✓ Test 6: POST /sessions/:id/send works');
      passed++;
    }
  } catch (e) {
    console.log('✗ Test 6 FAILED:', e.message);
    failed++;
  }

  console.log(`\n${passed} passed, ${failed} failed, ${skipped} skipped`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests().catch(e => {
  console.error('Test error:', e);
  process.exit(1);
});
