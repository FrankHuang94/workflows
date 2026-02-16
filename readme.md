# Semiconductor Daily Digest

This program collects global semiconductor-industry news from the last 24 hours focused on:

- strategy
- finance
- semiconductor company earnings
- investment
- fundraising
- new product releases
- major events

It sends a summary email every morning at **8:00 AM PST/PDT**.

## Setup

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure email credentials via environment variables (see `.env.example`).

## Usage

### Run once immediately (recommended for testing)

```bash
python semiconductor_digest.py --run-once --dry-run
```

- `--dry-run` prints the summary to stdout without sending email.
- Remove `--dry-run` to send email.

### Run as a daily scheduler

```bash
python semiconductor_digest.py
```

This runs continuously and executes the digest job at **08:00 America/Los_Angeles** every day.

## Deployment tip

For an always-on setup, run this with a process manager (e.g., systemd, Docker restart policy, or PM2) on a machine/server that remains online.


## Deploy directly on GitHub (recommended)

You can run this automatically from **GitHub Actions** so your laptop does not need to stay on.

1. Push this repository to GitHub.
2. In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Add these secrets:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `EMAIL_SENDER`
   - `EMAIL_RECIPIENT`
4. The workflow file `.github/workflows/semiconductor-digest.yml` runs daily and sends the digest at **8:00 AM America/Los_Angeles**.
5. You can also trigger it manually from **Actions → Semiconductor Daily Digest → Run workflow**.

### If you want me to deploy to your GitHub now

I can do it once you provide your repository URL (and ensure this environment has push access). Then I can add the remote, push the branch, and you can set the GitHub Secrets in the web UI.
