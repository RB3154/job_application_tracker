# Deploying to AWS

How to run the app on AWS as a Docker container: the image lives in ECR, the container runs on EC2, and the data lives in RDS PostgreSQL.

[← Back to the README](../README.md)

---

## What Goes Where

```text
Browser --http:80--> EC2 server [ Docker container: FastAPI on port 8000 ]
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

> **No HTTPS yet.** Without a domain or HTTPS, passwords and login cookies travel
> unencrypted. Use a throwaway password until [HTTPS](#adding-https-before-real-use) is added.

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
| `jat-web` | SSH, port 22 | **My IP** only |
| `jat-db` | PostgreSQL, port 5432 | The `jat-web` security group |

The database is never open to the internet. Only the server can reach it.

## 4. Create the Database

RDS → Create database:

- Engine: **PostgreSQL**, template: **Free tier**
- Master password: letters and numbers only, so it's safe inside `DATABASE_URL`
- **Public access: No**, security group: `jat-db`
- Additional configuration → **Initial database name**: `job_tracker`. RDS doesn't
  create it unless you fill this in.

Wait until it's *Available*, then copy its **endpoint**.

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
- Security group: `jat-web`
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
FRONTEND_URL=http://ELASTIC_IP
COOKIE_SECURE=false
TZ=Asia/Kolkata
```

- Don't put quote marks around values: Docker keeps them as part of the value.
- Don't add S3 keys: the server's role replaces them.
- `?ssl=require` is the spelling this app's database driver needs. `sslmode=require`
  crashes it.
- `TZ` is your own timezone. Without it the server uses UTC, so "today" can be a day off
  around midnight.

## 8. Run the App

```bash
IMAGE=ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com/job-tracker:latest

aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.ap-southeast-2.amazonaws.com
docker pull $IMAGE

# Create the tables
docker run --rm --env-file ~/.env $IMAGE alembic upgrade head

# Check that the role and hop limit let the container use S3
docker run --rm --env-file ~/.env $IMAGE python check_s3.py

# Start the app. It restarts by itself after a crash or reboot
docker run -d --name jat --restart unless-stopped --env-file ~/.env -p 80:8000 $IMAGE
```

Visit `http://ELASTIC_IP/health`. It should show `{"status":"healthy"}`.

## 9. Check That It Works

- Register, log in, and add a company, job and application.
- Upload a profile picture.
- Log in as a second user and check you can't see the first user's data.
- Enter a wrong password 6 times in a minute. The last attempt should say "Too many attempts".
- Run `docker restart jat`. Your data should still be there.
- From your PC, check that `http://ELASTIC_IP:8000` doesn't load.

---

## Updating the App

On your PC, run the two `docker build` and `docker push` commands from step 2. Then on
the server:

```bash
docker pull $IMAGE
docker run --rm --env-file ~/.env $IMAGE alembic upgrade head
docker rm -f jat
docker run -d --name jat --restart unless-stopped --env-file ~/.env -p 80:8000 $IMAGE
```

## Useful Commands

| Command | What it does |
| --- | --- |
| `docker logs -f jat` | Follow the app's logs (Ctrl+C to stop) |
| `docker ps` | Show running containers |
| `docker restart jat` | Restart the app |
| `df -h` / `free -h` | Check disk space and memory |

## Troubleshooting

| Problem | Likely cause |
| --- | --- |
| Site doesn't load | `jat-web` is missing port 80, or the container stopped: check `docker ps -a` and `docker logs jat` |
| `/health` shows "Database unavailable" | `jat-db` doesn't allow `jat-web`, or `DATABASE_URL` is wrong |
| `TypeError` mentioning `sslmode` | Use `?ssl=require` in `DATABASE_URL` |
| Picture upload fails | Hop limit isn't 2, or the role is missing the S3 policy: run `check_s3.py` |
| Can't stay logged in | `COOKIE_SECURE=true` without HTTPS |
| Reset link points to localhost | `FRONTEND_URL` isn't set |
| Reset email never arrives | Mailtrap's sandbox catches all email: check the Mailtrap inbox |

---

## Adding HTTPS (Before Real Use)

Put [Caddy](https://caddyserver.com/) in front of the app. It gets and renews HTTPS
certificates by itself. It needs a domain, or a free address like `1-2-3-4.sslip.io`.

Doing this also means changing:

1. **The security group:** open port 443.
2. **`.env`:** `COOKIE_SECURE=true` and `FRONTEND_URL=https://your-address`.
3. **`Dockerfile`:** turn proxy headers on and trust only Caddy, so the rate limiter
   sees real visitors instead of Caddy. Never use `--forwarded-allow-ips '*'` while the
   container can be reached directly, because anyone could then fake their IP.
4. **`main.py`:** add the `Strict-Transport-Security` header.

Password reset emails also need a real mail provider instead of the Mailtrap sandbox.
