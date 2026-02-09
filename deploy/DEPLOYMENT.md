# Wordly deployment (Linux + Nginx + Certbot)

These instructions assume the code is installed at `/home/wordly/wordly` and a
`wordly` user already exists on the server. Adjust paths as needed.

## 1) System packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nodejs npm nginx certbot python3-certbot-nginx
```

## 2) App install (as the wordly user)

```bash
sudo -u wordly -H bash -lc "git clone <repo_url> /home/wordly/wordly"
```

### Backend setup

```bash
sudo -u wordly -H bash -lc "cd /home/wordly/wordly/backend \
  && python3 -m venv .venv \
  && . .venv/bin/activate \
  && pip install -r requirements.txt"
```

Create the admin code file if it does not already exist:

```bash
sudo -u wordly -H bash -lc "cd /home/wordly/wordly/backend \
  && printf '%s\n' 'replace-with-admin-code' > admin_code.txt"
```

### Frontend build

```bash
sudo -u wordly -H bash -lc "cd /home/wordly/wordly/frontend \
  && npm install \
  && VITE_API_BASE_URL=/api npm run build"
```

## 3) systemd service

Copy the example service file and enable it:

```bash
sudo cp /home/wordly/wordly/deploy/wordly.service /etc/systemd/system/wordly.service
sudo systemctl daemon-reload
sudo systemctl enable --now wordly.service
sudo systemctl status wordly.service
```

The service uses a Unix socket at `/home/wordly/wordly.sock`. Ensure Nginx can
read it (the service runs with `Group=www-data` by default).

## 4) Nginx configuration

Copy the Nginx config and enable it:

```bash
sudo cp /home/wordly/wordly/deploy/nginx.conf /etc/nginx/sites-available/wordly
sudo ln -s /etc/nginx/sites-available/wordly /etc/nginx/sites-enabled/wordly
sudo nginx -t
sudo systemctl reload nginx
```

The config expects the built frontend at `/home/wordly/wordly/frontend/dist`
and proxies `/api/` requests to the Gunicorn socket.

## 5) TLS certificates with Certbot

```bash
sudo certbot --nginx -d wordly.qclub.au
```

Certbot will inject the SSL directives into the Nginx server block. After
issuance, reload Nginx if needed:

```bash
sudo systemctl reload nginx
```

## 6) Verifying

```bash
curl -I https://wordly.qclub.au
curl https://wordly.qclub.au/api/config
```

## 7) Updating the deployment

```bash
sudo -u wordly -H bash -lc "cd /home/wordly/wordly && git pull"
sudo -u wordly -H bash -lc "cd /home/wordly/wordly/backend \
  && . .venv/bin/activate \
  && pip install -r requirements.txt"
sudo -u wordly -H bash -lc "cd /home/wordly/wordly/frontend \
  && npm install \
  && VITE_API_BASE_URL=/api npm run build"
sudo systemctl restart wordly.service
sudo systemctl reload nginx
```
