# Deployment Checklist ✅

Use this checklist to ensure your voice AI bot is properly configured and ready for production.

## Pre-Deployment

### Environment Setup
- [ ] Python 3.11+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created from `.env.example`

### API Credentials
- [ ] Twilio Account SID configured
- [ ] Twilio Auth Token configured
- [ ] Twilio Phone Number configured
- [ ] Sarvam AI API Key configured
- [ ] Server URL configured (HTTPS)

### Configuration Validation
- [ ] All required environment variables set
- [ ] Knowledge base file exists (`knowledge/Querie.json`)
- [ ] Log directories created (`logs/`, `debug_audio/`)
- [ ] File permissions correct

## Testing

### Local Testing
- [ ] Application starts without errors
- [ ] Health check endpoint responds (`/health`)
- [ ] Analytics endpoint responds (`/analytics`)
- [ ] WebSocket endpoint accessible (`/media-stream`)

### Twilio Integration
- [ ] Webhook URL configured in Twilio Console
- [ ] Webhook URL uses HTTPS
- [ ] Phone number webhook points to `/voice/incoming`
- [ ] Test call connects successfully

### Voice Pipeline
- [ ] IVR menu plays correctly
- [ ] Language selection works (digits 1-4)
- [ ] WebSocket connection establishes
- [ ] Audio flows bidirectionally
- [ ] STT transcribes correctly
- [ ] LLM generates responses
- [ ] TTS synthesizes speech
- [ ] User can interrupt bot

### Checkpoint Verification
- [ ] CHECKPOINT 0: Bot starts
- [ ] CHECKPOINT 1-4: Pipeline builds
- [ ] CHECKPOINT 5: Audio received
- [ ] CHECKPOINT 6-7: VAD works
- [ ] CHECKPOINT 8: STT succeeds
- [ ] CHECKPOINT 9-10: Aggregator works
- [ ] CHECKPOINT 11-12: LLM responds
- [ ] CHECKPOINT 13-14: TTS generates
- [ ] CHECKPOINT FINAL: Call ends cleanly

## Production Readiness

### Security
- [ ] API keys stored securely (not in code)
- [ ] HTTPS/WSS enabled (no HTTP/WS)
- [ ] CORS configured appropriately
- [ ] Rate limiting considered
- [ ] Input validation in place
- [ ] Error messages don't leak sensitive info

### Performance
- [ ] VAD parameters tuned (stop_secs=0.8)
- [ ] Aggregation timeout optimized (0.8s)
- [ ] Audio resampling correct (8kHz for Twilio)
- [ ] Connection pooling configured
- [ ] Timeout values appropriate (15-20s)

### Monitoring
- [ ] Logging configured (loguru)
- [ ] Log rotation enabled
- [ ] Error logs separate
- [ ] Analytics tracking enabled
- [ ] Health check endpoint monitored

### Error Handling
- [ ] Retry logic in place (STT, LLM, TTS)
- [ ] Fallback responses configured
- [ ] Timeout handling implemented
- [ ] Resource cleanup on errors
- [ ] Graceful degradation

### Scalability
- [ ] Session storage strategy defined
- [ ] Database for analytics (if needed)
- [ ] Load balancer configuration (if needed)
- [ ] Horizontal scaling plan
- [ ] Resource limits set

## Docker Deployment

### Docker Setup
- [ ] Dockerfile exists and builds
- [ ] docker-compose.yml configured
- [ ] Environment variables in docker-compose
- [ ] Volumes configured for logs
- [ ] Health check in Dockerfile
- [ ] Port mapping correct (8000:8000)

### Docker Testing
- [ ] Image builds successfully
- [ ] Container starts without errors
- [ ] Health check passes
- [ ] Logs accessible via docker-compose
- [ ] Application accessible from host

## Cloud Deployment

### Infrastructure
- [ ] Cloud provider selected (AWS/GCP/Azure)
- [ ] Instance type/size appropriate
- [ ] Network configuration correct
- [ ] Firewall rules configured
- [ ] SSL/TLS certificate installed

### Domain & DNS
- [ ] Domain name registered
- [ ] DNS records configured
- [ ] SSL certificate valid
- [ ] HTTPS redirects enabled
- [ ] WebSocket support verified

### Backup & Recovery
- [ ] Backup strategy defined
- [ ] Configuration backed up
- [ ] Database backups (if applicable)
- [ ] Disaster recovery plan
- [ ] Rollback procedure documented

## Post-Deployment

### Verification
- [ ] Make test call from external number
- [ ] Verify all languages work
- [ ] Test interruption handling
- [ ] Check audio quality
- [ ] Verify latency acceptable (< 1s)

### Monitoring Setup
- [ ] Log aggregation configured
- [ ] Metrics collection enabled
- [ ] Alerts configured
- [ ] Dashboard created
- [ ] On-call rotation defined

### Documentation
- [ ] README updated
- [ ] API documentation current
- [ ] Deployment guide complete
- [ ] Troubleshooting guide available
- [ ] Runbook created

### Team Handoff
- [ ] Team trained on system
- [ ] Access credentials shared securely
- [ ] Support procedures documented
- [ ] Escalation path defined
- [ ] Knowledge transfer complete

## Maintenance

### Regular Tasks
- [ ] Monitor logs daily
- [ ] Review analytics weekly
- [ ] Update dependencies monthly
- [ ] Rotate API keys quarterly
- [ ] Review security annually

### Performance Tuning
- [ ] Monitor API response times
- [ ] Optimize VAD parameters
- [ ] Tune LLM parameters
- [ ] Adjust timeout values
- [ ] Review resource usage

### Updates
- [ ] Keep dependencies updated
- [ ] Monitor Pipecat releases
- [ ] Update Sarvam AI models
- [ ] Review Twilio changes
- [ ] Test updates in staging

## Troubleshooting Checklist

### If calls don't connect:
- [ ] Check Twilio webhook configuration
- [ ] Verify SERVER_URL is correct
- [ ] Check firewall rules
- [ ] Review Twilio logs
- [ ] Test webhook URL manually

### If audio doesn't flow:
- [ ] Check WebSocket connection
- [ ] Verify audio format (8kHz mulaw)
- [ ] Check VAD configuration
- [ ] Review transport logs
- [ ] Enable debug audio

### If STT fails:
- [ ] Verify Sarvam API key
- [ ] Check audio quality (RMS)
- [ ] Review buffer size
- [ ] Check language code
- [ ] Enable debug logging

### If LLM fails:
- [ ] Verify API credentials
- [ ] Check message format
- [ ] Review context size
- [ ] Check timeout values
- [ ] Review fallback responses

### If TTS fails:
- [ ] Verify API credentials
- [ ] Check text format
- [ ] Review audio resampling
- [ ] Check language code
- [ ] Enable debug audio

## Sign-Off

### Development Team
- [ ] Code reviewed
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Deployment tested

### Operations Team
- [ ] Infrastructure ready
- [ ] Monitoring configured
- [ ] Backups enabled
- [ ] Runbook reviewed

### Product Team
- [ ] Requirements met
- [ ] User testing complete
- [ ] Acceptance criteria satisfied
- [ ] Launch approved

---

**Date**: _______________

**Deployed By**: _______________

**Approved By**: _______________

**Notes**:
_______________________________________
_______________________________________
_______________________________________

---

## Quick Reference

### Essential URLs
- Application: `https://your-domain.com`
- Health Check: `https://your-domain.com/health`
- Analytics: `https://your-domain.com/analytics`
- Twilio Console: `https://console.twilio.com`

### Essential Commands
```bash
# Start application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Check health
curl https://your-domain.com/health

# View logs
tail -f logs/app_*.log

# Docker logs
docker-compose logs -f
```

### Emergency Contacts
- On-Call Engineer: _______________
- Twilio Support: _______________
- Sarvam AI Support: _______________

---

**✅ All checks complete? You're ready to deploy!**
