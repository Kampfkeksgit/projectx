# Discord Bot Dashboard - Integration Test Plan

## System Components
- ✓ Python Discord Bot
- ✓ Node.js Express Backend
- ✓ Vue.js Frontend Dashboard
- ✓ SQLite Database
- ✓ Discord OAuth2 Authentication

## Test Scenarios

### 1. Authentication Flow
- [ ] User clicks "Login with Discord"
- [ ] Redirected to Discord OAuth screen
- [ ] After authorization, receives code
- [ ] Backend exchanges code for tokens
- [ ] Tokens stored in localStorage
- [ ] User info displayed in navbar
- [ ] Subsequent API calls include Bearer token
- [ ] Token refresh works on 401

### 2. Guild Management
- [ ] User can view list of guilds
- [ ] Guild icons display correctly
- [ ] Guild names display correctly
- [ ] Owner/Admin badges display correctly
- [ ] Clicking guild navigates to dashboard
- [ ] Selected guild ID saved to localStorage

### 3. Welcome Message Configuration
- [ ] Settings load from backend
- [ ] Enable/disable toggle works
- [ ] Channel ID input accepts values
- [ ] Message textarea shows default placeholder
- [ ] Preview updates in real-time as typing
- [ ] {user} placeholder replaced with "@User" in preview
- [ ] {guild} placeholder replaced with server name in preview
- [ ] Save button sends PUT request to backend
- [ ] Success message displays after save
- [ ] Settings persist after page reload
- [ ] Reset button reverts to last saved state

### 4. Leave Message Configuration
- [ ] Settings load from backend
- [ ] Enable/disable toggle works
- [ ] Channel ID input accepts values
- [ ] Message textarea shows default placeholder
- [ ] Preview updates in real-time as typing
- [ ] {user} placeholder replaced with "User" in preview
- [ ] {guild} placeholder replaced with server name in preview
- [ ] Save button sends PUT request to backend
- [ ] Success message displays after save
- [ ] Settings persist after page reload
- [ ] Reset button reverts to last saved state

### 5. Backend API Integration
- [ ] Health check endpoint responds (GET /api/health)
- [ ] Auth callback accepts code (POST /api/auth/callback)
- [ ] Auth callback returns tokens
- [ ] Token refresh endpoint works (POST /api/auth/refresh)
- [ ] Guilds list endpoint returns user's guilds (GET /api/guilds)
- [ ] Guild details endpoint works (GET /api/guilds/:id)
- [ ] Guild combined endpoint works (GET /api/guilds/:id/full)
- [ ] Settings get endpoint returns data (GET /api/guilds/:id/settings)
- [ ] Settings put endpoint saves data (PUT /api/guilds/:id/settings)
- [ ] Settings patch endpoint merges data (PATCH /api/guilds/:id/settings)
- [ ] Audit logging records changes
- [ ] Invalid token returns 401
- [ ] Unauthorized guild access returns 403

### 6. Bot Functionality
- [ ] Bot connects to Discord (logged in status)
- [ ] Bot can read guild settings from database
- [ ] Welcome message sends on member join
- [ ] Welcome message uses configured channel
- [ ] Welcome message uses configured template
- [ ] {user} placeholder replaced with @username
- [ ] {guild} placeholder replaced with server name
- [ ] Leave message sends on member leave
- [ ] Leave message uses configured channel
- [ ] Leave message uses configured template
- [ ] !welcome_test command works (admin only)
- [ ] Bot respects enabled/disabled settings

### 7. Database
- [ ] Guilds table has correct records
- [ ] Guild settings table has correct data
- [ ] Users table stores user info correctly
- [ ] User guilds relationship is correct
- [ ] Audit log records all changes
- [ ] Foreign key constraints work
- [ ] Timestamps are correct

### 8. Error Handling
- [ ] Missing token returns 401
- [ ] Invalid token returns 401
- [ ] Unauthorized guild access returns 403
- [ ] Invalid channel ID shows error message
- [ ] API timeout shows error message
- [ ] Network error shows error message
- [ ] Database error shows generic error
- [ ] Graceful logout on token refresh failure

### 9. Frontend User Experience
- [ ] NavBar shows login button when not authenticated
- [ ] NavBar shows user avatar/name when authenticated
- [ ] NavBar logout clears all data
- [ ] Loading spinners show during API calls
- [ ] Success/error/info messages display correctly
- [ ] Error messages auto-dismiss after 3 seconds
- [ ] Buttons disable during loading
- [ ] Responsive layout works on mobile
- [ ] Dark theme colors are consistent

### 10. Multi-Guild Support
- [ ] User can access multiple guilds
- [ ] Settings for each guild are independent
- [ ] Changing settings in one guild doesn't affect others
- [ ] Guild selector shows all user's guilds
- [ ] Can switch between guilds quickly

## Test Environment Setup

1. **Discord Bot Token**: Add to X:\projectx\bot\.env
2. **Backend running**: npm run dev on port 3000
3. **Frontend running**: npm run dev on port 5173
4. **Bot running**: python main.py
5. **Test Discord server**: Use a private test server

## Manual Testing Steps

### Before Testing:
1. Create a test Discord server
2. Add the bot to the server
3. Create channels for welcome/leave messages
4. Note the channel IDs

### Test Workflow:
1. Open http://localhost:5173
2. Click "Login with Discord"
3. Authorize the app
4. Select test server
5. Configure welcome message with test channel ID
6. Configure leave message with test channel ID
7. Have a user join the server (or test bot)
8. Verify welcome message sends
9. Have a user leave the server
10. Verify leave message sends
11. Modify settings and verify changes persist
12. Test logout functionality

## Automated Test Commands

```bash
# Backend tests
cd X:\projectx\backend
npm test

# Frontend tests (if implemented)
cd X:\projectx\frontend
npm test
```

## Known Issues / Notes

- Discord API rate limiting may occur during testing
- Bot requires "Send Messages" permission in configured channels
- User must be in guild to configure it

## Approval Checklist

- [ ] All 10 test scenarios pass
- [ ] No console errors in browser
- [ ] No console errors in backend
- [ ] No console errors in bot
- [ ] Database integrity verified
- [ ] Performance acceptable (no major lag)
- [ ] Error handling works correctly
- [ ] Ready for production deployment
