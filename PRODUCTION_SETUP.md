# Production Deployment Guide

## Pre-Deployment Checklist

### Security
- [ ] Change all default credentials
- [ ] Generate new SESSION_SECRET for backend
- [ ] Use HTTPS/TLS for all connections
- [ ] Configure firewall rules
- [ ] Set up rate limiting
- [ ] Enable input validation
- [ ] Review CORS configuration
- [ ] Remove debug endpoints
- [ ] Verify no secrets in code
- [ ] Enable security headers

### Database
- [ ] Create database backup strategy
- [ ] Set up automated backups
- [ ] Configure database permissions
- [ ] Enable database encryption
- [ ] Create database indexes
- [ ] Test database recovery

### Infrastructure
- [ ] Set up web server (Nginx/Apache)
- [ ] Configure SSL/TLS certificates
- [ ] Set up load balancing
- [ ] Configure caching
- [ ] Set up CDN for static assets
- [ ] Configure auto-scaling if needed

### Monitoring
- [ ] Set up error logging (Sentry/similar)
- [ ] Configure uptime monitoring
- [ ] Set up performance monitoring
- [ ] Configure alerts for critical issues
- [ ] Set up log aggregation
- [ ] Create dashboards

### Deployment
- [ ] Set up CI/CD pipeline
- [ ] Create deployment scripts
- [ ] Set up staging environment
- [ ] Test deployment process
- [ ] Document rollback procedures
- [ ] Create health check endpoints

## Production Deployment Steps

### 1. Backend Deployment

```bash
# Clone repository to production server
git clone <repo> /var/www/projectx-backend

# Navigate to backend
cd /var/www/projectx-backend/backend

# Install dependencies
npm install --production

# Copy production environment file
cp .env.production .env

# Configure environment variables
nano .env  # Edit all variables

# Create data directory
mkdir -p /data

# Start application
npm start
```

### 2. Frontend Deployment

```bash
# Clone repository
git clone <repo> /var/www/projectx-frontend

# Navigate to frontend
cd /var/www/projectx-frontend/frontend

# Install dependencies
npm install

# Copy production environment file
cp .env.production .env

# Configure environment variables
nano .env  # Edit all variables

# Build for production
npm run build

# Copy built files to web server
cp -r dist/* /var/www/html/
```

### 3. Bot Deployment

```bash
# Clone repository
git clone <repo> /var/www/projectx-bot

# Navigate to bot
cd /var/www/projectx-bot/bot

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy production environment file
cp .env.production .env

# Configure environment variables
nano .env  # Edit all variables

# Create systemd service for bot
sudo nano /etc/systemd/system/projectx-bot.service
```

### 4. Nginx Configuration Example

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    root /var/www/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API
    location /api {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Environment Variables Reference

### Backend
- `PORT` - Server port (default 3000)
- `NODE_ENV` - Environment (production/development)
- `DISCORD_CLIENT_ID` - Discord app ID
- `DISCORD_CLIENT_SECRET` - Discord app secret
- `DISCORD_REDIRECT_URI` - OAuth redirect URL
- `FRONTEND_URL` - Frontend domain
- `DATABASE_URL` - Database file path
- `SESSION_SECRET` - Random session secret
- `CORS_ORIGIN` - Allowed frontend origin

### Frontend
- `VITE_BACKEND_URL` - Backend API URL
- `VITE_DISCORD_CLIENT_ID` - Discord app ID
- `VITE_DISCORD_REDIRECT_URI` - OAuth redirect URL

### Bot
- `DISCORD_TOKEN` - Bot token
- `DISCORD_CLIENT_ID` - Discord app ID
- `DISCORD_CLIENT_SECRET` - Discord app secret
- `BACKEND_URL` - Backend API URL
- `DATABASE_URL` - Database file path

## Verification

After deployment, verify:

```bash
# Check backend health
curl https://yourdomain.com/api/health

# Check bot status
# Connect to Discord and verify bot is online

# Check frontend
# Open https://yourdomain.com in browser and verify pages load

# Test OAuth flow
# Click login and verify redirect works

# Test settings save
# Configure welcome/leave messages and verify they save

# Test bot functionality
# Have user join server and verify welcome message sends
```

## Troubleshooting

### Backend not responding
- Check nginx logs: `tail -f /var/log/nginx/error.log`
- Check backend logs: `pm2 logs`
- Verify backend is running: `ps aux | grep node`
- Check firewall: `sudo ufw status`

### Frontend not loading
- Check nginx logs
- Verify build was successful: `ls dist/`
- Check browser console for errors
- Verify API URL is correct

### Bot not connecting
- Check bot token is valid
- Verify intents are enabled
- Check logs: `pm2 logs projectx-bot`
- Verify backend URL is accessible

### Database issues
- Check database file permissions: `ls -la /data/bot.db`
- Verify database exists: `sqlite3 /data/bot.db ".tables"`
- Check database size: `du -h /data/bot.db`

## Rollback Plan

If deployment fails:

1. Stop services
2. Restore previous backup
3. Revert environment variables
4. Restart services
5. Verify functionality
6. Investigate issues

## Ongoing Maintenance

### Weekly
- Check error logs
- Monitor disk space
- Review performance metrics
- Check for security patches

### Monthly
- Update dependencies
- Review and optimize queries
- Analyze performance trends
- Test backup restoration

### Quarterly
- Security audit
- Performance review
- Capacity planning
- Disaster recovery drill

## Support

For issues during deployment:
1. Check logs for specific errors
2. Review this guide
3. Consult ARCHITECTURE.md
4. Review TEST_PLAN.md for expected behavior
