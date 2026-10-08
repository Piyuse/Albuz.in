# Stills

For a public Vercel frontend with a separate Django host, see [DEPLOYMENT.md](DEPLOYMENT.md).

Stills combines the [Rotator bookshelf design](https://github.com/Piyuse/Rotator) with this Django API. Users can create albums, upload their own photos, browse them as books, and import selected photos from a shared Google Drive folder they can access. JPEG, PNG, and WebP photos can be up to 300 MB and 80 million pixels each. MPO multi-picture JPEG files with `.jpg` names are also accepted as JPEG photos. Device upload batches can contain up to 3,000 MB; Google Drive imports can contain up to ten selected photos. Large Drive downloads spill to temporary disk storage and are uploaded one at a time. Reimporting the same Drive file into the same album is skipped. An older album photo without a recorded Drive ID is compared byte for byte on retry and linked when identical; historical duplicate entries are not deleted automatically. A production proxy and application server must allow the corresponding request size and processing time, and the host needs sufficient temporary and permanent storage.

In **View all albums**, each album card has a **Delete album** button. An open album also has **Delete album** in its header and **Delete photo** on each photo page. **Manage album** shows a photo list with delete buttons as well. Deletion is soft: the `isdeleted` database column becomes `1`, `deleted_at` records the time, and photo files and database records remain. Deleted items disappear from album listings and shared links. Importing a previously deleted Drive photo again restores its existing album record without downloading a second copy. The photo cleanup command keeps files referenced by soft-deleted records.

## Run locally

Use Python 3.11+ and Node.js 20+. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open **http://127.0.0.1:5173**. The Vite server proxies `/api` to Django. The default configuration uses SQLite and stores uploads in `private-media`; file URLs are signed and expire after one hour.

To serve one built application from Django, run `npm run build` in `frontend`, then `manage.py collectstatic --noinput`. Set `FRONTEND_URL=http://127.0.0.1:8000` in `.env`, restart Django, and open **http://127.0.0.1:8000**.

## Google Drive import

Create a Google Cloud OAuth **web application**, enable the Drive API, and add `http://127.0.0.1:8000/api/integrations/google/callback/` as an authorized redirect URI. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` in `.env`. Generate a persistent encryption key:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set its output as `GOOGLE_TOKEN_ENCRYPTION_KEY`. Restart Django after editing `.env`. In an album's **Manage album** view, connect Google Drive, paste a shared folder URL, select up to ten photos, and import. The connected Google account must have access to the folder. The API downloads the selected images and stores copies in the album; it does not depend on the original folder afterward.

While the OAuth app is in **Testing**, open the same Google Cloud project that owns `GOOGLE_CLIENT_ID`, then go to **Google Auth Platform → Audience → Test users → Add users**. Add the exact Google accounts that will connect to Drive, including developer accounts. An account outside this list receives Google's `403 access_denied` page before the callback reaches Django. This project requests `drive.readonly`, a restricted scope; broad public access requires Google's restricted-scope verification and may require a security assessment. Publishing without completing the applicable verification does not make this testing error a backend issue.

For local development, Stills accepts the frontend at either `127.0.0.1:5173` or `localhost:5173` and returns to the address where the connection started. The Google Cloud authorized redirect URI must still exactly match `GOOGLE_REDIRECT_URI`. For production, set `DJANGO_DEBUG=false`, a strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `FRONTEND_URL`, HTTPS, and persistent database and storage credentials.

After updating the project, run `manage.py migrate` and restart Django and Vite. Begin a new Google connection; earlier OAuth attempts cannot use the updated flow. OAuth attempts expire after ten minutes. Failed callbacks return to the Stills interface with an error message.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
Set-Location frontend
npm run build
```
