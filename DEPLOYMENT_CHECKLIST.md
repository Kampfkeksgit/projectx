# Deployment Preparation Checklist

## Environment Variables

### Bot (.env)
- [ ] DISCORD_TOKEN set (bot token from Discord dev portal)
- [ ] DISCORD_CLIENT_ID set
- [ ] DISCORD_CLIENT_SECRET set
- [ ] BACKEND_URL set (production backend URL)
- [ ] DATABASE_URL set (production database path)

### Backend (.env)
- [ ] PORT set (usually 3000)
- [ ] DISCORD_CLIENT_ID set
- [ ] DISCORD_CLIENT_SECRET set
- [ ] DISCORD_REDIRECT_URI set (production URL)
- [ ] FRONTEND_URL set (production frontend URL)
- [ ] DATABASE_URL set (production database path)
- [ ] SESSION_SECRET set (random string)
- [ ] NODE_ENV set to "production"

### Frontend (.env)
- [ ] VITE_BACKEND_URL set (production backend URL)
- [ ] VITE_DISCORD_CLIENT_ID set
- [ ] VITE_DISCORD_REDIRECT_URI set (production URL)

## Database
- [ ] SQLite database backed up
- [ ] Database migration scripts tested
- [ ] Database permissions correct

## Security
- [ ] No secrets in version control
- [ ] .gitignore configured correctly
- [ ] HTTPS enabled for production
- [ ] CORS properly restricted to production domains
- [ ] Rate limiting implemented
- [ ] Input validation in place

## Performance
- [ ] Frontend built for production (npm run build)
- [ ] Backend in production mode
- [ ] Database indexes optimized
- [ ] API response times acceptable

## Monitoring
- [ ] Logging configured
- [ ] Error tracking enabled
- [ ] Health checks in place
- [ ] Uptime monitoring configured

## Documentation
- [ ] README.md created
- [ ] API documentation updated
- [ ] Deployment guide written
- [ ] User guide written
