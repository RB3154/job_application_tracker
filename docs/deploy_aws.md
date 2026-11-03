# Deploying to AWS

How to run the app on AWS as a Docker container: the image lives in ECR, the container runs on EC2, and the data lives in RDS PostgreSQL.

[← Back to the README](../README.md)

---

## What Goes Where

```text
Browser --https:443--> EC2 server [ Caddy container --> app container: FastAPI on port 8000 ]
                                                          |--> RDS PostgreSQL (private, EC2 only)
                                                          |--> S3 bucket (profile pictures)

Your PC --docker push--> ECR (private image store) --docker pull--> EC2
```

| AWS service | What it is | Used for |
| --- | --- | --- |
| ECR | A private store for Docker images | Holding the app's image |
| EC2 | A rented server | Running the container |
| RDS | A PostgreSQL database that AWS looks after | The app's data, with automatic backups |
| IAM role | Permissions given to a server, instead of passwords | Letting EC2 use S3 and ECR without keys |
| Security group | A firewall | Deciding who can reach the server and database |
| Caddy | A web server that sits in front of the app | HTTPS, with free certificates it gets and renews by itself |

> **HTTPS without buying a domain.** [sslip.io](https://sslip.io) turns an IP address into a
> name: `52-64-121-241.sslip.io` points to `52.64.121.241`. Certificates need a name, so
> this is what Caddy uses. Replace `ELASTIC_IP` below with your own address, and
> `ELASTIC-IP` with the same address written with dashes.

> **Cost.** On new accounts the free tier is credits, not free forever. The free plan
> ends after 6 months or when the credits run out. EC2, RDS and public IP addresses all
> use credits while they exist, so check the Billing page. Stop or delete anything you
> aren't using.

Use the same region for everything: **ap-southeast-2 (Sydney)**, where the S3 bucket is.
Pick it in the top-right corner of the AWS console before creating anything.

---

## 1. Prepare the Account

1. **Billing alert:** Billing → Budgets → create a monthly budget with an email alert.
2. **Root user:** turn on MFA, and don't create access keys for it.
3. **IAM user for your PC:** create one with access to ECR. Create an access key for it.
4. **AWS CLI:** install it on your PC, then run `aws configure` and enter that key and
   the region `ap-southeast-2`.
5. Check that the S3 bucket `jat-fastapi-project` is in this account.

## 2. Build and Push the Image

In the ECR console, create a **private repository** named `job-tracker`. Then, from the
project folder in PowerShell, replacing `ACCOUNT_ID` with your 12-digit account number:

```powershell
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com

docker build --platform linux/amd64 -t ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/job-tracker:latest .
docker push ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/job-tracker:latest
```

## 3. Create the Firewalls

In EC2 → Security Groups, create two:

| Name | Allow incoming | From |
| --- | --- | --- |
| `jat-web` | HTTP, port 80 | Anywhere |
| `jat-web` | HTTPS, port 443 | Anywhere |
| `jat-web` | SSH, port 22 | **My IP** only |
| `jat-db` | PostgreSQL, port 5432 | The `jat-web` security group |

The database is never open to the internet. Only the server can reach it.

Port 80 stays open even with HTTPS. Caddy uses it to get its certificate and to send
`http://` visitors to `https://`.

## 4. Create the Database

RDS → Create database:

- Engine: **PostgreSQL**, template: **Free tier**
- Master password: letters and numbers only, so it's safe inside `DATABASE_URL`
- **Public access: No**, security group: `jat-db`
- Additional configuration → **Initial database name**: `job_tracker`. RDS doesn't
  create it unless you fill this in.

Wait until it's *Available*, then copy its **endpoint**.

If you forgot the initial database name, `alembic upgrade head` in step 8 fails with
`database "job_tracker" does not exist`. You can create it from the server, after setting
`IMAGE` and pulling the image as in step 8:

```bash
docker run --rm --env-file ~/.env $IMAGE python -c "
import asyncio, os, asyncpg
async def main():
    url = os.environ['DATABASE_URL'].split('?')[0].rsplit('/', 1)[0] + '/postgres'
    conn = await asyncpg.connect(url, ssl='require')
    await conn.execute('CREATE DATABASE job_tracker')
    await conn.close()
asyncio.run(main())
"
```

## 5. Create the Server's Role

IAM → Roles → Create role → trusted entity **EC2**. Attach:

- `AmazonEC2ContainerRegistryReadOnly`, to download the image
- A new policy with the contents of `aws_iam_policy_rudy_jat.json`, to use the S3 folder

Name it `jat-ec2-role`.

## 6. Create the Server

EC2 → Launch instance:

- Image: **Amazon Linux 2023**, architecture **64-bit (x86)**
- Type: one labelled **Free tier eligible**, such as `t3.micro`
- Key pair: create one and keep the file safe
- Network settings → **Edit** → **Select existing security group** → `jat-web`. If you
  leave the default, AWS makes a new group called `launch-wizard-1`, and the database
  won't let the server in. To fix it afterwards: Instances → Actions → Security →
  Change security groups → add `jat-web`.
- Advanced details → IAM instance profile: `jat-ec2-role`
- Advanced details → **Metadata response hop limit: 2**. The container sits one extra
  network step away from the server, so with 1 it can't use the role and S3 fails.

Then EC2 → Elastic IPs → allocate one and associate it with the server, so its address
doesn't change on restart.

## 7. Set Up the Server

```bash
ssh -i your-key.pem ec2-user@ELASTIC_IP

sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
exit
```

Log back in so the group change applies, then create the settings file:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # copy this for SECRET_KEY
nano ~/.env
chmod 600 ~/.env
```

```env
DATABASE_URL=postgresql://USERNAME:PASSWORD@RDS_ENDPOINT:5432/job_tracker?ssl=require
SECRET_KEY=PASTE_THE_NEW_KEY
S3_BUCKET_NAME=jat-fastapi-project
S3_REGION=ap-southeast-2
MAIL_SERVER=sandbox.smtp.mailtrap.io
MAIL_PORT=2525
MAIL_USERNAME=YOUR_MAILTRAP_USERNAME
MAIL_PASSWORD=YOUR_MAILTRAP_PASSWORD
MAIL_FROM=noreply@example.com
MAIL_USE_TLS=true
FRONTEND_URL=https://ELASTIC-IP.sslip.io
COOKIE_SECURE=true
TZ=Asia/Kolkata
```

- Don't put quote marks around values: Docker keeps them as part of the value.
- Don't add S3 keys: the server's role replaces them.
- `?ssl=require` is the spelling this app's database driver needs. `sslmode=require`
  crashes it.
- `TZ` is your own timezone. Without it the server uses UTC, so "today" can be a day off
  around midnight.
- `COOKIE_SECURE=true` only sends the login cookie over HTTPS. Keep it `true`, because
  the site is only reached through Caddy.

Then create Caddy's settings file:

```bash
mkdir -p ~/caddy
nano ~/caddy/Caddyfile
```

```text
ELASTIC-IP.sslip.io {
	reverse_proxy jat:8000
	header Strict-Transport-Security "max-age=31536000"
}

http://ELASTIC_IP {
	redir https://ELASTIC-IP.sslip.io{uri} permanent
}
```

- The first block serves the site over HTTPS and passes every request to the app.
- `Strict-Transport-Security` tells browsers to always use HTTPS for this site.
- The second block sends anyone who types the bare IP to the HTTPS address.

## 8. Run the App

```bash
IMAGE=ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/job-tracker:latest

aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com
docker pull $IMAGE

# Create the tables
docker run --rm --env-file ~/.env $IMAGE alembic upgrade head

# Check that the role and hop limit let the container use S3
docker run --rm --env-file ~/.env $IMAGE python check_s3.py

# A private network for the two containers, with fixed addresses
docker network create --subnet 172.20.0.0/24 jat-net

# Start Caddy. It is the only container open to the internet
docker run -d --name caddy --restart unless-stopped --network jat-net --ip 172.20.0.2 \
  -p 80:80 -p 443:443 \
  -v ~/caddy/Caddyfile:/etc/caddy/Caddyfile:ro -v caddy_data:/data -v caddy_config:/config \
  caddy:2

# Start the app. It has no -p, so only Caddy can reach it
docker run -d --name jat --restart unless-stopped --env-file ~/.env \
  --network jat-net --ip 172.20.0.10 $IMAGE \
  fastapi run main.py --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips 172.20.0.2
```

- Both containers restart by themselves after a crash or a reboot.
- The words after `$IMAGE` replace the Dockerfile's start command. They let the app trust
  the visitor's real IP sent by Caddy, **and only Caddy** (`172.20.0.2`), so the login
  rate limit sees real visitors and nobody can fake their IP.
- `caddy_data` keeps the certificate, so restarting Caddy doesn't ask for a new one.
- Run `docker logs caddy`. Look for `certificate obtained successfully`.

Visit `https://ELASTIC-IP.sslip.io/health`. It should show `{"status":"healthy"}` with
a padlock in the address bar.

## 9. Check That It Works

- Register, log in, and add a company, job and application.
- Upload a profile picture.
- Log in as a second user and check you can't see the first user's data.
- Enter a wrong password 6 times in a minute. The last attempt should say "Too many attempts".
- Run `docker restart jat`. Your data should still be there.
- From your PC, check that `http://ELASTIC_IP:8000` doesn't load.
- Check that `http://ELASTIC_IP` jumps to the `https://` address.

---

## Updating the App

On your PC, run the two `docker build` and `docker push` commands from step 2. Then on
the server:

```bash
docker pull $IMAGE
docker run --rm --env-file ~/.env $IMAGE alembic upgrade head
docker rm -f jat
docker run -d --name jat --restart unless-stopped --env-file ~/.env \
  --network jat-net --ip 172.20.0.10 $IMAGE \
  fastapi run main.py --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips 172.20.0.2
```

Caddy keeps running. You only restart it after you change the Caddyfile:
`docker restart caddy`.

## Useful Commands

| Command | What it does |
| --- | --- |
| `docker logs -f jat` | Follow the app's logs (Ctrl+C to stop) |
| `docker logs caddy` | Caddy's logs: certificates and HTTPS errors |
| `docker ps` | Show running containers |
| `docker restart jat` | Restart the app |
| `df -h` / `free -h` | Check disk space and memory |

## Troubleshooting

| Problem | Likely cause |
| --- | --- |
| Site doesn't load | `jat-web` is missing port 80 or 443, or a container stopped: check `docker ps -a`, `docker logs caddy` and `docker logs jat` |
| Can't SSH in, or nothing answers at all | Make sure the server uses `jat-web`. If a fresh server was stuck "Initializing", terminate it and launch a new one |
| `/health` shows "Database unavailable", or `alembic` times out | The server isn't in `jat-web` (check for `launch-wizard-1`), `jat-db` doesn't allow `jat-web`, or `DATABASE_URL` is wrong |
| `database "job_tracker" does not exist` | The initial database name was left empty: see step 4 |
| `docker: Address already in use` when starting Caddy | Another container took `172.20.0.2`. Start Caddy first, or give every container a fixed `--ip` |
| Caddy logs show certificate errors | Port 80 isn't open to everyone, or the sslip.io name doesn't match the Elastic IP |
| `TypeError` mentioning `sslmode` | Use `?ssl=require` in `DATABASE_URL` |
| Picture upload fails | Hop limit isn't 2, or the role is missing the S3 policy: run `check_s3.py` |
| Can't stay logged in | You opened the site over `http://`: use the `https://` address |
| Everyone gets "Too many attempts" together | The app is trusting the wrong IP: check `--forwarded-allow-ips 172.20.0.2` matches Caddy's `--ip` |
| Reset link points to localhost | `FRONTEND_URL` isn't set |
| Reset email never arrives | Mailtrap's sandbox catches all email: check the Mailtrap inbox |

---

## Before Real Use

- **Real email:** password reset emails need a real mail provider instead of the Mailtrap
  sandbox, which catches every email.
- **Your own domain (optional):** to use one, point it at the Elastic IP, then put it in
  the Caddyfile and in `FRONTEND_URL` in place of the sslip.io name.
- **Never use `--forwarded-allow-ips '*'`.** It would let anyone fake their IP and get
  around the login rate limit.
