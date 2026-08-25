# Deploying SIPETIK (Laravel) to Vercel

This project is a full Laravel 12 app (Blade views, `routes/web_with_api.php`,
DB-backed controllers), not a static frontend. `vite build` only compiles
`resources/css`/`resources/js` into `public/build` — it does not make the PHP
app itself run. To serve it on Vercel we run PHP through the community
[`vercel-php`](https://github.com/vercel-community/php) runtime as a
serverless function, and route every non-static request to it.

## What changed

- **`vercel.json`** — builds the Vite assets into `public` (the Output
  Directory Vercel was missing before), and runs `api/index.php` as a PHP
  serverless function via `vercel-php@0.9.0`. All requests are rewritten to
  that function except files that physically exist in `public/`
  (`public/build/*`, `favicon.ico`, `robots.txt`, ...), which are served as
  static files directly.
- **`api/index.php`** — a copy of `public/index.php` used as the Vercel
  function entrypoint (Vercel expects functions under `/api`).
- **`.vercelignore`** — keeps `vendor/`, `node_modules/`, the training
  pipeline, and the `.pt` model weights out of the deployment upload.
- `vercel.json`'s `env` block points Laravel's cache/compiled-view/log paths
  at `/tmp`, the only writable directory in a Vercel function, and switches
  `SESSION_DRIVER` to `cookie`, `CACHE_STORE` to `array`, and
  `QUEUE_CONNECTION` to `sync` — see "Why these driver changes" below.

## Required manual setup (can't be done from the repo alone)

### 1. A Supabase (Postgres) database
`DB_HOST=127.0.0.1` only exists on your own machine. We're using
[Supabase](https://supabase.com) for the cloud database — it's Postgres, and
Laravel already ships a ready `pgsql` connection in `config/database.php`.
The migrations in this project use Laravel's schema builder in a portable
way (checked — no raw MySQL-specific SQL), so nothing else needs to change
for the switch from MySQL to Postgres.

`vercel.json`'s `env` block already sets `DB_CONNECTION=pgsql` and
`DB_SSLMODE=require` (Supabase requires TLS). What's still needed:

- Create a Supabase project (any region close to your users — e.g.
  Southeast Asia/Singapore — is fine; it doesn't need to match Vercel's
  region).
- In the project's **Connect** dialog, use the **Session pooler**
  connection details (port 5432, IPv4) — not the Direct connection (IPv6
  only by default, often unreachable from serverless platforms) and not the
  Transaction pooler for now. The Session pooler behaves like a normal
  Postgres connection, so Laravel's default prepared-statement handling
  works without extra packages. If you outgrow the Session pooler's
  connection ceiling later, the Transaction pooler (port 6543) offers more
  headroom for serverless, but PgBouncer's transaction mode doesn't support
  prepared statements — you'd need a compatibility package (e.g.
  `vermaysha/pgbouncer-laravel-extension`, currently beta) or to set
  `PDO::ATTR_EMULATE_PREPARES => true` on the `pgsql` connection's
  `options` in `config/database.php` first.
- Set `DB_HOST`, `DB_PORT` (5432), `DB_DATABASE` (usually `postgres`),
  `DB_USERNAME`, `DB_PASSWORD` from that connection string as **Environment
  Variables in the Vercel Project Settings** — never commit real DB
  credentials to `vercel.json` or `.env`.
- Run migrations once against that database from your machine: point your
  local `.env` at the Supabase connection temporarily and run
  `php artisan migrate --force` (or `vercel env pull` if you use the Vercel
  CLI, then migrate). Vercel's build step intentionally does **not** run
  migrations automatically — that would risk running them against
  production on every push, including preview deployments.

Bonus: Supabase Storage also exposes an S3-compatible API, so it can double
as the persistent image storage mentioned in step 3 below — one provider
instead of two.

### 2. `APP_KEY` and other secrets, as Vercel Environment Variables
Generate one with `php artisan key:generate --show` and add it (and
`OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `ROBOFLOW_API_KEY` / Reverb keys
you actually use) under Vercel → Project → Settings → Environment Variables.
`SESSION_DRIVER=cookie` still signs/encrypts cookies with `APP_KEY`, so this
is required for login/CSRF to work at all.

### 3. Persistent storage for uploaded/captured images
`app/Http/Controllers/Api/CameraController.php` and
`BuzzerControlController.php` write to local storage. Vercel functions only
have `/tmp`, which is **not shared between invocations and not publicly
served** — so images saved there disappear and can't be viewed. If the
dashboard needs to keep and display camera captures, switch
`FILESYSTEM_DISK` to an S3-compatible bucket (AWS S3, Cloudflare R2,
DigitalOcean Spaces, etc.), add `league/flysystem-aws-s3-v3` via Composer,
and set the `AWS_*` env vars (already present as placeholders in
`.env.example`). Happy to wire this up once you've picked a provider.

## Why these driver changes

| Setting | Local default | Vercel value | Why |
|---|---|---|---|
| `SESSION_DRIVER` | `database` | `cookie` | No shared writable disk/DB session table dependency for basic requests; sessions ride in a signed cookie instead. |
| `CACHE_STORE` | `database` | `array` | In-memory per-request cache; avoids writing to a DB cache table on every deploy/cold start. |
| `QUEUE_CONNECTION` | `database` | `sync` | Vercel functions are stateless/short-lived — nothing runs `queue:work`, so queued jobs would sit forever. `sync` runs jobs inline instead. |
| `LOG_CHANNEL` | `stack` | `stderr` | `storage/logs` isn't writable; `stderr` is captured in Vercel's function logs. |

If you'd rather keep database-backed sessions/cache/queue, that's fine too —
just make sure the DB is reachable and understand queued jobs won't process
automatically without a separate always-on worker (Vercel can't run one).

## Deploy steps, in order

1. Create the Supabase project and run migrations against it once (Session pooler connection).
2. Add all secrets (`APP_KEY`, `DB_*`, API keys) in Vercel → Environment
   Variables (Production, and Preview if you want preview deploys to work
   too).
3. Push this branch / merge to `main` (or whichever branch Vercel deploys
   from) to trigger a deploy.
4. Watch the build logs — the `vercel-php` runtime runs `composer install`
   for `api/index.php` automatically; no changes needed for that.
5. If pages 500, check Vercel's function logs (Deployments → the deployment
   → Logs) — with `LOG_CHANNEL=stderr` Laravel's errors show up there.
