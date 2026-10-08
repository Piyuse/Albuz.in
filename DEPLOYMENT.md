# Deploy Stills: Vercel + Render + Aiven MySQL + Cloudflare R2

This guide uses Vercel for the Vite frontend, Render Free Web Service for Django, Aiven Free for MySQL, and Cloudflare R2 Standard for private photos. Render Free sleeps after 15 minutes without traffic, so the first request can take about a minute. Render says its free service is for hobby/testing use. Aiven Free has no availability SLA and may be powered off after inactivity. R2 usage above its monthly free allowance can be billed. Use paid hosting for a dependable public service.

## 0. Push the deployment files to GitHub

From the repository root in PowerShell:

```powershell
git branch --show-current
git status --short
git add .env.example .dockerignore Dockerfile config/settings.py frontend/src/scene.js DEPLOYMENT.md README.md
git commit -m "Prepare split deployment"
git push origin frontend_integration
```

The first command must print `frontend_integration`. Review `git status` before staging anything else. Do not commit `.env`, database files, private media, or credentials. Hosting services deploy pushed commits, not uncommitted files. Skip the commit if these files are already pushed.

## 1. Create MySQL on Aiven

1. Create an [Aiven account](https://console.aiven.io/). In a project, choose **Services → Create service → MySQL → Free**. Name the service and create it. The Free tier currently includes 1 GB storage and backups; it does not let you choose the cloud region.
2. Open the MySQL service **Overview / Connection information**. Copy the **host**, **port**, **user**, **password**, and **database** (`defaultdb` unless changed). Keep the password private.
3. Download its **CA certificate**. Open the `.pem` file in a text editor and copy all of it, including `BEGIN CERTIFICATE` and `END CERTIFICATE`. You will add it to Render as a secret file named `aiven-ca.pem`.

Django's first startup runs `manage.py migrate` and creates the tables in Aiven. This makes an empty production database; it does **not** transfer data from local SQLite or MySQL.

## 2. Create private photo storage on Cloudflare R2

1. Open [Cloudflare R2](https://dash.cloudflare.com/) under **Storage & databases → R2**. Activate R2 and review its subscription/checkout terms before continuing.
2. Choose **Create bucket**, give it a name such as `stills-private-photos`, select **Standard** storage, and leave public access disabled.
3. Under **R2 → Overview → Manage API Tokens**, create an R2 token with **Object Read & Write** access limited to that bucket. Copy the **Access Key ID**, **Secret Access Key**, and **S3 API endpoint**. The secret is shown only once.
4. Later set `S3_BUCKET` to the bucket name, `S3_REGION` to `auto`, and `S3_ENDPOINT_URL` to `https://ACCOUNT_ID.r2.cloudflarestorage.com`. The AWS-named environment variables below contain the R2 token values.
5. After you know the exact Vercel production URL, open the bucket's **Settings → CORS Policy → Add CORS policy → JSON** and save this policy, replacing the example origin. The 3D room loads album covers as WebGL textures, which require this browser permission even for signed private URLs:

```json
[
  {
    "AllowedOrigins": ["https://stills-albums.vercel.app"],
    "AllowedMethods": ["GET", "HEAD"]
  }
]
```

The app generates one-hour signed URLs for private photos. R2 Standard currently includes 10 GB-month storage, 1 million Class A requests, and 10 million Class B requests each month free. Soft-deleted photos stay in R2, so storage continues to grow.

## 3. Deploy Django on Render

1. Sign in to [Render](https://dashboard.render.com/) with GitHub access. Choose **New → Web Service** and select this repository.
2. Set **Branch** to `frontend_integration`, **Root Directory** to the repository root (leave it empty), **Language/Runtime** to **Docker**, and **Instance Type** to **Free**. Render uses this repository's `Dockerfile`; leave Build and Start Command overrides empty.
3. Pick a service name such as `stills-api`. Render gives it a URL such as `https://stills-api.onrender.com`. Substitute your actual URL in every setting below.
4. Before deploying, add these values in the Render **Environment** settings. For `FRONTEND_URL`, choose an expected Vercel production URL, then replace it with the actual one in step 4. Do not add a trailing slash.

| Render variable | Value |
| --- | --- |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | New long random key; keep it unchanged |
| `DJANGO_ALLOWED_HOSTS` | `stills-api.onrender.com` (host only, no `https://`) |
| `DJANGO_TRUST_PROXY_SSL_HEADER` | `true` for Render's HTTPS proxy |
| `FRONTEND_URL` | `https://stills-albums.vercel.app` (replace with exact Vercel production origin) |
| `DB_NAME` | Aiven database, usually `defaultdb` |
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Copy each value from Aiven |
| `DB_SSL_CA` | `/etc/secrets/aiven-ca.pem` |
| `S3_BUCKET` | Your private R2 bucket name |
| `S3_REGION` | `auto` |
| `S3_ENDPOINT_URL` | Your R2 S3 API endpoint, including `https://` |
| `AWS_ACCESS_KEY_ID` | R2 Access Key ID |
| `AWS_SECRET_ACCESS_KEY` | R2 Secret Access Key |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth Web application client; can be added after step 5 |
| `GOOGLE_REDIRECT_URI` | `https://stills-api.onrender.com/api/integrations/google/callback/` (include final slash) |
| `GOOGLE_TOKEN_ENCRYPTION_KEY` | Stable Fernet key; set before using Google Drive |

Generate the two keys locally and paste their output **only** into Render's Environment settings:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

5. Add a Render **Secret File**. Filename: `aiven-ca.pem`. Contents: the complete CA certificate downloaded from Aiven. Keep `DB_SSL_CA=/etc/secrets/aiven-ca.pem`; the backend verifies the MySQL server's certificate and hostname.
6. Deploy. The Docker image installs MySQL's native driver and Django packages, collects Django static files, runs database migrations on startup, and launches Gunicorn. Wait for **Live**; inspect **Logs** if it fails. The backend root `/` can show a frontend-build message; the user-facing site will be on Vercel.

Render Free has no separate pre-deploy command or shell. Migrations run on each startup and are idempotent. Back up the database before schema changes.

## 4. Deploy the Vite frontend on Vercel

1. In [Vercel](https://vercel.com/new), choose **Add New → Project** and import the same GitHub repository. Set **Root Directory** to `frontend`.
2. Set **Framework Preset** to **Vite**, **Install Command** to `npm ci`, **Build Command** to `npm run build`, and **Output Directory** to `dist`.
3. Add a **Production** environment variable `VITE_API_BASE_URL=https://stills-api.onrender.com` using your real Render URL. This is a public URL, not a secret.
4. Deploy. Open **Project → Settings → Environments → Production → Branch Tracking** and set the production branch to `frontend_integration`. If Vercel initially deployed `main`, trigger a new production deployment from `frontend_integration` and use that production URL. Future pushes to that branch deploy automatically.
5. Copy the stable Vercel production URL (`https://...vercel.app`, or a custom domain). Update Render's `FRONTEND_URL` to **exactly** that origin, without a trailing slash or path, and save/redeploy Render. Do not use a changing preview URL for Google connections.

`VITE_` variables are embedded in public JavaScript. Never put `DJANGO_SECRET_KEY`, database passwords, R2 credentials, or Google secrets there or in Git. The browser sends `/api/` calls directly to Render, avoiding Vercel Function upload limits and proxy timeouts.

## 5. Configure Google Drive OAuth

1. In [Google Cloud Console](https://console.cloud.google.com/), select the project that owns the OAuth client and enable the **Google Drive API**.
2. In **Google Auth Platform**, configure the consent screen and request `https://www.googleapis.com/auth/drive.readonly`. Create or edit an OAuth **Web application** client.
3. Add the backend `GOOGLE_REDIRECT_URI` above as an **Authorized redirect URI**, matching every character, especially `https://` and the final `/`. Put the client ID and secret in Render and redeploy.
4. While the Google app is in **Testing**, add the exact Google accounts that will connect Drive as **Test users**. Test from the stable Vercel production URL.

Google classifies `drive.readonly` as a restricted scope. People outside the test-user list can receive `403 access_denied` until applicable Google verification is complete; this can include a security assessment. Testing authorizations may expire after seven days. A public Vercel site alone does not make Drive permission public.

## 6. Check the running application

1. Open the Vercel production URL. Register a user, create an album, upload a small photo, reload, and confirm it persists. Then test a larger photo, Google Drive import, and delete controls.
2. In browser Developer Tools → Network, API requests should go to your Render HTTPS hostname. Image URLs should be signed R2 URLs. An API CORS error usually means Render's `FRONTEND_URL` differs from the page's exact origin. An image/texture CORS error usually means R2's bucket CORS policy has the wrong origin.
3. If the backend shows a gateway error, inspect Render **Logs**. Common causes are incorrect Aiven host/port/password/CA, R2 endpoint, a missing environment variable, or the backend waking from sleep.
4. Back up database and photo objects. Securely save `DJANGO_SECRET_KEY` and `GOOGLE_TOKEN_ENCRYPTION_KEY`; losing the latter makes existing encrypted Google connections unreadable.

**Large-file limit:** The application allows 300 MB per photo, but that size has **not** been verified on Render Free. Its small instance and traffic allowance make large uploads/imports unreliable. Test realistic files before inviting users; use a paid backend or a direct-to-R2 upload design if large files are essential. The current app has no registration rate limits or upload quotas, so do not advertise open registration broadly before adding abuse controls.

Official references: [Render Free limits](https://render.com/docs/free), [Render Docker deploys](https://render.com/docs/docker), [Render secret files](https://render.com/docs/configure-environment-variables), [Aiven MySQL Free](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier), [Aiven MySQL setup](https://aiven.io/docs/products/mysql/get-started), [Cloudflare R2 setup](https://developers.cloudflare.com/r2/get-started/s3/), [Cloudflare R2 CORS](https://developers.cloudflare.com/r2/buckets/cors/), [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/), [Vercel Git production branch](https://vercel.com/docs/git), [Google OAuth verification](https://support.google.com/cloud/answer/13463073).
