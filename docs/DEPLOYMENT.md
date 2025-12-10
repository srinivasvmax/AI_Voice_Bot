# Deployment Guide

## Production Deployment Options

### 1. Docker Deployment (Recommended)

#### Prerequisites
- Docker and Docker Compose installed
- Domain with SSL certificate
- Twilio account configured

#### Steps

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd voice-ai-bot
   cp .env.example .env
   # Edit .env with production values
   ```

2. **Build and run**
   ```bash
   docker-compose up -d
   ```

3. **Check logs**
   ```bash
   docker-compose logs -f
   ```

4. **Configure Twilio webhook**
   - Set webhook URL to: `https://your-domain.com/voice/incoming`

### 2. Cloud Platform Deployment

#### AWS Elastic Beanstalk

1. **Install EB CLI**
   ```bash
   pip install awsebcli
   ```

2. **Initialize**
   ```bash
   eb init -p python-3.11 voice-ai-bot
   ```

3. **Create environment**
   ```bash
   eb create voice-ai-bot-prod
   ```

4. **Set environment variables**
   ```bash
   eb setenv TWILIO_ACCOUNT_SID=xxx SARVAM_API_KEY=yyy ...
   ```

5. **Deploy**
   ```bash
   eb deploy
   ```

#### Google Cloud Run

1. **Build container**
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/voice-ai-bot
   ```

2. **Deploy**
   ```bash
   gcloud run deploy voice-ai-bot \
     --image gcr.io/PROJECT_ID/voice-ai-bot \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

3. **Set environment variables**
   ```bash
   gcloud run services update voice-ai-bot \
     --set-env-vars TWILIO_ACCOUNT_SID=xxx,SARVAM_API_KEY=yyy
   ```

#### Azure Container Instances

1. **Create resource group**
   ```bash
   az group create --name voice-ai-bot-rg --location eastus
   ```

2. **Deploy container**
   ```bash
   az container create \
     --resource-group voice-ai-bot-rg \
     --name voice-ai-bot \
     --image your-registry/voice-ai-bot:latest \
     --dns-name-label voice-ai-bot \
     --ports 8000 \
     --environment-variables \
       TWILIO_ACCOUNT_SID=xxx \
       SARVAM_API_KEY=yyy
   ```

### 3. Kubernetes Deployment

#### Create Kubernetes manifests

**deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-ai-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voice-ai-bot
  template:
    metadata:
      labels:
        app: voice-ai-bot
    spec:
      containers:
      - name: voice-ai-bot
        image: your-registry/voice-ai-bot:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: voice-ai-bot-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

**service.yaml**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: voice-ai-bot
spec:
  selector:
    app: voice-ai-bot
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

**Deploy**
```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## SSL/TLS Configuration

### Using Let's Encrypt with Nginx

1. **Install Certbot**
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   ```

2. **Obtain certificate**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

3. **Nginx configuration**
   ```nginx
   server {
       listen 443 ssl http2;
       server_name your-domain.com;
       
       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

## Monitoring & Logging

### Application Monitoring

1. **Prometheus + Grafana**
   - Add prometheus-fastapi-instrumentator
   - Configure metrics endpoint
   - Set up Grafana dashboards

2. **DataDog**
   ```python
   # Add to requirements.txt
   ddtrace
   
   # Run with DataDog
   ddtrace-run python -m uvicorn app.main:app
   ```

3. **New Relic**
   ```bash
   pip install newrelic
   newrelic-admin run-program python -m uvicorn app.main:app
   ```

### Log Aggregation

1. **ELK Stack**
   - Configure Filebeat to ship logs
   - Set up Elasticsearch for storage
   - Use Kibana for visualization

2. **CloudWatch (AWS)**
   ```python
   # Install watchtower
   pip install watchtower
   
   # Configure in logging_config.py
   import watchtower
   logger.add(watchtower.CloudWatchLogHandler())
   ```

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer**
   - Use AWS ALB, GCP Load Balancer, or Nginx
   - Enable sticky sessions for WebSocket connections

2. **Session Storage**
   - Replace in-memory storage with Redis
   - Configure Redis cluster for high availability

3. **Database**
   - Add PostgreSQL for persistent analytics
   - Use connection pooling

### Vertical Scaling

- **CPU**: 2-4 cores per instance
- **Memory**: 2-4 GB per instance
- **Network**: High bandwidth for audio streaming

## Security Checklist

- [ ] Use HTTPS/WSS only
- [ ] Store secrets in environment variables or secrets manager
- [ ] Enable rate limiting
- [ ] Implement API authentication
- [ ] Configure CORS properly
- [ ] Use security headers
- [ ] Enable firewall rules
- [ ] Regular security updates
- [ ] Monitor for suspicious activity
- [ ] Implement request validation

## Performance Optimization

1. **Connection Pooling**
   - Configure httpx connection limits
   - Use persistent connections

2. **Caching**
   - Cache knowledge base in memory
   - Use Redis for session caching

3. **Async Operations**
   - All I/O operations are async
   - Use asyncio.gather for parallel operations

4. **Resource Limits**
   - Set max concurrent connections
   - Configure timeout values
   - Implement circuit breakers

## Backup & Recovery

1. **Database Backups**
   - Daily automated backups
   - Point-in-time recovery
   - Test restore procedures

2. **Configuration Backups**
   - Version control for configs
   - Backup environment variables
   - Document all settings

3. **Disaster Recovery**
   - Multi-region deployment
   - Automated failover
   - Regular DR drills

## Health Checks

```bash
# Application health
curl https://your-domain.com/health

# Detailed status
curl https://your-domain.com/analytics

# Kubernetes liveness probe
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

## Troubleshooting

### Common Issues

1. **WebSocket connection fails**
   - Check SSL/TLS configuration
   - Verify proxy settings
   - Check firewall rules

2. **High latency**
   - Check network connectivity
   - Monitor API response times
   - Review resource utilization

3. **Memory leaks**
   - Monitor memory usage
   - Check for unclosed connections
   - Review cleanup procedures

### Debug Mode

```bash
# Enable debug logging
DEBUG=true python -m uvicorn app.main:app

# Save debug audio
SAVE_DEBUG_AUDIO=true python -m uvicorn app.main:app
```

## Support

For deployment issues:
1. Check logs: `docker-compose logs -f`
2. Review documentation
3. Open GitHub issue
4. Contact support team
