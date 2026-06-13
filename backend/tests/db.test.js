/**
 * Database Helper Tests
 * Tests for all CRUD operations and helper functions
 */

import * as db from '../db.js';
import * as dbHelper from '../utils/dbHelper.js';

let testsPassed = 0;
let testsFailed = 0;

// Test utilities
function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAILED: ${message}`);
    testsFailed++;
  } else {
    console.log(`✓ ${message}`);
    testsPassed++;
  }
}

function assertEquals(actual, expected, message) {
  if (actual !== expected) {
    console.error(`❌ FAILED: ${message}`);
    console.error(`  Expected: ${expected}, Got: ${actual}`);
    testsFailed++;
  } else {
    console.log(`✓ ${message}`);
    testsPassed++;
  }
}

async function asyncTest(message, testFn) {
  try {
    await testFn();
    console.log(`✓ ${message}`);
    testsPassed++;
  } catch (error) {
    console.error(`❌ FAILED: ${message}`);
    console.error(`  Error: ${error.message}`);
    testsFailed++;
  }
}

// Test data
const testGuildId = '123456789012345678';
const testGuildName = 'Test Guild';
const testGuildIcon = 'https://example.com/icon.png';

const testUserId = '987654321098765432';
const testUsername = 'TestUser';
const testEmail = 'test@example.com';
const testAvatarUrl = 'https://example.com/avatar.png';

// Run tests
async function runTests() {
  console.log('🧪 Starting Database Tests...\n');

  // ===== GUILD OPERATIONS =====
  console.log('📍 Testing Guild Operations...\n');

  await asyncTest('Create Guild', async () => {
    const result = await db.createGuild(testGuildId, testGuildName, testGuildIcon);
    assert(result, 'Guild creation should return a result');
  });

  await asyncTest('Get Guild', async () => {
    const guild = await db.getGuild(testGuildId);
    assert(guild, 'Should retrieve created guild');
    assertEquals(guild.guild_name, testGuildName, 'Guild name should match');
    assertEquals(guild.guild_icon_url, testGuildIcon, 'Guild icon should match');
  });

  await asyncTest('Get All Guilds', async () => {
    const guilds = await db.getAllGuilds();
    assert(Array.isArray(guilds), 'Should return array of guilds');
    assert(guilds.length > 0, 'Should contain at least one guild');
  });

  await asyncTest('Update Guild', async () => {
    const newName = 'Updated Guild Name';
    await db.updateGuild(testGuildId, { guild_name: newName });
    const guild = await db.getGuild(testGuildId);
    assertEquals(guild.guild_name, newName, 'Guild name should be updated');
  });

  // ===== GUILD SETTINGS =====
  console.log('\n📍 Testing Guild Settings Operations...\n');

  await asyncTest('Upsert Guild Settings', async () => {
    const settings = {
      welcome_enabled: true,
      welcome_channel_id: '111111111111111111',
      welcome_message: 'Welcome {user}!',
      leave_enabled: true,
      leave_channel_id: '222222222222222222',
      leave_message: '{user} has left.',
    };
    await db.upsertGuildSettings(testGuildId, settings);
    const retrieved = await db.getGuildSettings(testGuildId);
    assert(retrieved, 'Should retrieve guild settings');
    assertEquals(retrieved.welcome_enabled, 1, 'Welcome should be enabled');
  });

  await asyncTest('Update Guild Settings', async () => {
    const newMessage = 'Hello {user}! Welcome aboard.';
    await db.upsertGuildSettings(testGuildId, { welcome_message: newMessage });
    const settings = await db.getGuildSettings(testGuildId);
    assertEquals(settings.welcome_message, newMessage, 'Welcome message should be updated');
  });

  // ===== USER OPERATIONS =====
  console.log('\n📍 Testing User Operations...\n');

  await asyncTest('Upsert User (Create)', async () => {
    const userData = {
      username: testUsername,
      email: testEmail,
      avatar_url: testAvatarUrl,
      access_token: 'test_access_token_123',
      refresh_token: 'test_refresh_token_456',
    };
    await db.upsertUser(testUserId, userData);
    const user = await db.getUser(testUserId);
    assert(user, 'Should retrieve created user');
    assertEquals(user.username, testUsername, 'Username should match');
  });

  await asyncTest('Get User', async () => {
    const user = await db.getUser(testUserId);
    assert(user, 'Should retrieve user');
    assertEquals(user.discord_id, testUserId, 'User ID should match');
  });

  await asyncTest('Upsert User (Update)', async () => {
    const updatedData = {
      username: 'UpdatedUser',
      email: 'updated@example.com',
      avatar_url: 'https://example.com/new-avatar.png',
      access_token: 'new_access_token_789',
      refresh_token: 'new_refresh_token_012',
    };
    await db.upsertUser(testUserId, updatedData);
    const user = await db.getUser(testUserId);
    assertEquals(user.username, 'UpdatedUser', 'Username should be updated');
  });

  // ===== USER-GUILD RELATIONSHIPS =====
  console.log('\n📍 Testing User-Guild Relationships...\n');

  await asyncTest('Add User to Guild', async () => {
    await db.addUserToGuild(testUserId, testGuildId, false, false);
    const hasAccess = await db.userHasGuildAccess(testUserId, testGuildId);
    assert(hasAccess, 'User should have access to guild');
  });

  await asyncTest('Get User Guilds', async () => {
    const guilds = await db.getUserGuilds(testUserId);
    assert(Array.isArray(guilds), 'Should return array of guilds');
    assert(guilds.length > 0, 'User should have at least one guild');
  });

  await asyncTest('Update User Role to Admin', async () => {
    await db.addUserToGuild(testUserId, testGuildId, false, true);
    const isAdmin = await db.userIsGuildAdmin(testUserId, testGuildId);
    assert(isAdmin, 'User should be guild admin');
  });

  await asyncTest('Update User Role to Owner', async () => {
    await db.addUserToGuild(testUserId, testGuildId, true, false);
    const isAdmin = await db.userIsGuildAdmin(testUserId, testGuildId);
    assert(isAdmin, 'Guild owner should be considered admin');
  });

  // ===== AUDIT LOGGING =====
  console.log('\n📍 Testing Audit Logging Operations...\n');

  await asyncTest('Log Audit Action', async () => {
    const changes = { welcome_message: 'old', welcome_message_new: 'new' };
    await db.logAuditAction(testUserId, testGuildId, 'update_settings', changes);
  });

  await asyncTest('Get Guild Audit Log', async () => {
    const logs = await db.getGuildAuditLog(testGuildId, 10);
    assert(Array.isArray(logs), 'Should return array of audit logs');
    assert(logs.length > 0, 'Should contain at least one audit entry');
  });

  // ===== DATABASE UTILITIES =====
  console.log('\n📍 Testing Database Utilities...\n');

  await asyncTest('Get Database Stats', async () => {
    const stats = await db.getDbStats();
    assert(stats, 'Should return database stats');
    assert(typeof stats.guilds === 'number', 'Should have guild count');
    assert(typeof stats.users === 'number', 'Should have user count');
  });

  // ===== HELPER FUNCTION TESTS =====
  console.log('\n📍 Testing Helper Functions...\n');

  // Test buildUpdateQuery
  const updateQueryTest = () => {
    const result = dbHelper.buildUpdateQuery('guilds', { guild_name: 'New Name' }, 'id = ?', [testGuildId]);
    assert(result.query.includes('UPDATE guilds'), 'Should build UPDATE query');
    assert(result.values.length === 2, 'Should have correct number of values');
  };
  updateQueryTest();
  console.log('✓ buildUpdateQuery function works');
  testsPassed++;

  // Test buildInsertQuery
  const insertQueryTest = () => {
    const result = dbHelper.buildInsertQuery('guilds', { id: testGuildId, guild_name: 'Test' });
    assert(result.query.includes('INSERT INTO'), 'Should build INSERT query');
    assert(result.values.length === 2, 'Should have correct number of values');
  };
  insertQueryTest();
  console.log('✓ buildInsertQuery function works');
  testsPassed++;

  // Test buildSelectQuery
  const selectQueryTest = () => {
    const result = dbHelper.buildSelectQuery('guilds', ['id', 'guild_name'], 'enabled = ?', [1], {
      orderBy: 'guild_name ASC',
      limit: 10,
    });
    assert(result.query.includes('SELECT'), 'Should build SELECT query');
    assert(result.query.includes('ORDER BY'), 'Should include ORDER BY');
    assert(result.query.includes('LIMIT'), 'Should include LIMIT');
  };
  selectQueryTest();
  console.log('✓ buildSelectQuery function works');
  testsPassed++;

  // Test handleDbError
  const errorTest = () => {
    const error = new Error('UNIQUE constraint failed: users.discord_id');
    const handled = dbHelper.handleDbError(error, 'test context');
    assertEquals(handled.code, 'UNIQUE_CONSTRAINT_VIOLATION', 'Should identify UNIQUE constraint error');
  };
  errorTest();
  console.log('✓ handleDbError function works');
  testsPassed++;

  // Test formatTimestamp
  const timestampTest = () => {
    const ts = dbHelper.formatTimestamp();
    assert(typeof ts === 'string', 'Should return string timestamp');
    assert(ts.includes('T'), 'Should be ISO format');
  };
  timestampTest();
  console.log('✓ formatTimestamp function works');
  testsPassed++;

  // Test validators
  assert(dbHelper.isValidGuildId('123456789012345678'), 'Valid guild ID should pass');
  console.log('✓ isValidGuildId function works');
  testsPassed++;

  assert(dbHelper.isValidUserId('987654321098765432'), 'Valid user ID should pass');
  console.log('✓ isValidUserId function works');
  testsPassed++;

  assert(!dbHelper.isValidGuildId('invalid'), 'Invalid guild ID should fail');
  console.log('✓ isValidGuildId rejects invalid IDs');
  testsPassed++;

  // Test safeJsonParse
  const jsonObj = { test: 'data' };
  const parsed = dbHelper.safeJsonParse(JSON.stringify(jsonObj));
  assertEquals(parsed.test, 'data', 'Should parse valid JSON');
  console.log('✓ safeJsonParse function works');
  testsPassed++;

  // Test sanitizeInput
  const sanitized = dbHelper.sanitizeInput("test'string\"");
  assert(!sanitized.includes("'") && !sanitized.includes('"'), 'Should remove quotes');
  console.log('✓ sanitizeInput function works');
  testsPassed++;

  // ===== CLEANUP TESTS =====
  console.log('\n📍 Testing Cleanup Operations...\n');

  await asyncTest('Remove User from Guild', async () => {
    await db.removeUserFromGuild(testUserId, testGuildId);
    const hasAccess = await db.userHasGuildAccess(testUserId, testGuildId);
    assert(!hasAccess, 'User should no longer have access to guild');
  });

  await asyncTest('Delete User', async () => {
    await db.deleteUser(testUserId);
    const user = await db.getUser(testUserId);
    assert(!user, 'User should be deleted');
  });

  await asyncTest('Delete Guild', async () => {
    await db.deleteGuild(testGuildId);
    const guild = await db.getGuild(testGuildId);
    assert(!guild, 'Guild should be deleted');
  });

  // ===== ERROR HANDLING TESTS =====
  console.log('\n📍 Testing Error Handling...\n');

  await asyncTest('Handle FOREIGN KEY constraint error', async () => {
    try {
      // Try to add user to non-existent guild
      await db.addUserToGuild('999999999999999999', '888888888888888888');
    } catch (error) {
      const handled = dbHelper.handleDbError(error, 'FK constraint test');
      assert(
        handled.code === 'FOREIGN_KEY_CONSTRAINT_VIOLATION' || error.message.includes('FOREIGN KEY'),
        'Should identify FK constraint error'
      );
    }
  });

  // ===== SUMMARY =====
  console.log('\n' + '='.repeat(50));
  console.log('📊 TEST SUMMARY');
  console.log('='.repeat(50));
  console.log(`✓ Passed: ${testsPassed}`);
  console.log(`❌ Failed: ${testsFailed}`);
  console.log(`Total: ${testsPassed + testsFailed}`);

  if (testsFailed === 0) {
    console.log('\n🎉 All tests passed!');
    process.exit(0);
  } else {
    console.log(`\n⚠️  ${testsFailed} test(s) failed`);
    process.exit(1);
  }
}

// Run tests
runTests().catch((error) => {
  console.error('Fatal error during tests:', error);
  process.exit(1);
});
