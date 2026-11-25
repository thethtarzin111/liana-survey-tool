# Demo server (Azure for Students)

A shared demo of LianaSurvey for the Liana team and other students, on one
small Linux VM in the EU. It runs the same way as `npm run dev`:

- **PostgreSQL** with the demo data (Example Members Association).
- **The app:** `backend/scripts/local_gateway.py`, which runs every API in one
  process, on 127.0.0.1:8000. Answers are saved directly (no RabbitMQ), and
  "new responses" emails are only logged (mock adapter).
- **Caddy:** HTTPS (Let's Encrypt) and the built admin app. The admin app has a
  **login page with one login per demo organisation**. Survey links (`/r/...`)
  and `/health` need no login.
- **GitHub Actions:** after CI passes on `main`, "Deploy demo" builds the admin
  app, copies the release to the VM and installs it (`deploy.sh`).

There is no real login yet (that comes with LianaAccount): everyone who has a
login is that organisation's demo user and can change or delete any of its
surveys. There are two demo organisations, each with its own login on the
login page (`/login`):

| Organisation | Demo user | Email address |
|---|---|---|
| Example Members Association | Anna Virtanen | `anna.virtanen@example.org` |
| LUT Students | Mikko Korhonen | `mikko.korhonen@example.org` |

The app checks the password (`DEMO_LOGINS` in `/etc/lianasurvey/app.env`) and
sets a signed, HTTP-only session cookie for 7 days (`DEMO_SESSION_SECRET`).
"Sign out" in the user menu ends it and goes back to the login page. A login
cannot switch organisation, so the user menu has no switcher here, unlike
`npm run dev`. To show that one organisation never sees another's surveys or
answers, sign out and sign in as the other one. A new password ends the
sessions signed in with the old one.

"Continue: Liana Technologies", "Reset password" and "Privacy Policy" on the
login page are only shown, as in the prototype.
Use demo data only. Every deploy reloads the demo data, so deleted demo surveys
come back.

| File | What it does |
|---|---|
| `setup-server.sh` | Run once on a new VM: packages, database roles, secrets, app service, Caddy, deploy key |
| `deploy.sh` | Run by the workflow for each release: Python packages, migrations, switch, restart, health check (goes back to the previous release if it fails) |
| `../../scripts/prepare_db.py` | Migrations and demo data, as `npm run dev` does locally |
| `../../../.github/workflows/deploy-demo.yml` | The "Deploy demo" workflow |

## 1. Create the VM (once)

1. Sign up for **Azure for Students** with your LUT email:
   <https://azure.microsoft.com/free/students>. No credit card needed; it
   comes with $100 credit for 12 months.
2. In the Azure portal: **Create a resource > Virtual machine**.
   - Resource group: `lianasurvey-demo` (new)
   - Name: `lianasurvey-demo`
   - Region: an EU region, e.g. **(Europe) Sweden Central** or **North Europe**
   - Image: **Ubuntu Server 24.04 LTS - x64 Gen2**
   - Size: **Standard_B1s** (1 vCPU, 1 GB; the setup adds swap). Check the
     size is marked as eligible for free services.
   - Authentication: **SSH public key**, username `azureuser`. Download the
     private key (`.pem`) and keep it safe.
   - Inbound ports: **SSH (22), HTTP (80), HTTPS (443)**
   - Before **Create**, check the cost estimate on the Review page.
3. When it is ready, open the VM > **Overview > DNS name > Not configured**,
   set the DNS name label to e.g. `lianasurvey-demo` and save. The address is
   then `lianasurvey-demo.<region>.cloudapp.azure.com`; that is `SITE_ADDRESS`.
4. Optional but useful: **Cost Management > Budgets**, a budget of a few euros
   with an email alert.

## 2. Set up the server (once)

The repository is private, so copy the script from your checkout:

```sh
scp -i lianasurvey-demo.pem backend/infra/deploy/setup-server.sh \
  azureuser@lianasurvey-demo.swedencentral.cloudapp.azure.com:
ssh -i lianasurvey-demo.pem azureuser@lianasurvey-demo.swedencentral.cloudapp.azure.com
sudo SITE_ADDRESS=lianasurvey-demo.swedencentral.cloudapp.azure.com bash setup-server.sh
```

It takes a few minutes and ends by printing:

- the three GitHub secrets (`DEMO_HOST`, `DEMO_SSH_KEY`, `DEMO_KNOWN_HOSTS`), and
- the login page address and the two logins (the email addresses above and
  their passwords) to share.

All secrets stay on the server in `/etc/lianasurvey/` (database passwords,
link-signing key, demo passwords, session key). Running the script again keeps
them. A server set up before the second organisation or the login page gets the
missing password and session key the next time the script runs.

A server set up before the login page used the browser's password prompt. After
the release with the login page is deployed, run `setup-server.sh` again: it
removes the prompt from Caddy and gives the app the logins. The passwords stay
the same; people sign in with the email addresses instead of `liana` and
`lutstudents`. Until then the admin app does not load.

## 3. Connect GitHub (once)

In the repository: **Settings > Secrets and variables > Actions > New
repository secret**, add the three secrets exactly as printed. Then
**Actions > Deploy demo > Run workflow**. After that, every merge to `main`
deploys automatically once CI passes.

### LianaMailer API (optional)

LianaAutomation matches contacts by email, so the app looks newsletter readers'
email addresses up in LianaMailer before it sends their events. Add these
repository secrets the same way (the API user, secret and realm come from Liana):

| Secret | Example |
|---|---|
| `LIANAMAILER_API_HOST` | `rest.lianamailer.com` |
| `LIANAMAILER_API_USER` | the API user id |
| `LIANAMAILER_API_SECRET` | the API secret |
| `LIANAMAILER_API_REALM` | `EUR` (the default when left out) |

The next deploy puts them in the release's `.env`, readable only by the app user.
Or set them in `/etc/lianasurvey/app.env` on the server (they win over the
secrets), then `sudo systemctl restart lianasurvey`. Without them the Integrations
page says "Contact lookup: not set up", and newsletter readers' events wait in the
sync log as failed until they are set (then press Retry). A value must not
contain a single quote.

## 4. Share it

Send Liana and the students the address with the logins. You can give
someone only one organisation's login. Survey links and QR codes from the app
work for anyone, without a login.

## Day to day

| Task | Command (on the server) |
|---|---|
| App logs | `sudo journalctl -u lianasurvey -f` |
| HTTPS logs | `sudo journalctl -u caddy -f` |
| Restart the app | `sudo systemctl restart lianasurvey` |
| Show the demo passwords | `sudo grep -E '^(DEMO\|STUDENTS)_PASSWORD=' /etc/lianasurvey/secrets` |
| Change a demo password | edit `DEMO_PASSWORD` (Anna Virtanen) or `STUDENTS_PASSWORD` (Mikko Korhonen) in `/etc/lianasurvey/secrets`, then run `setup-server.sh` again |
| Which release is live | `readlink /opt/lianasurvey/current` |

To redeploy without a new commit: **Actions > Deploy demo > Run workflow**.

## Moving it later

- **Another Linux server** (e.g. one Liana provides): the same two scripts work
  on any Ubuntu 24.04 machine with a DNS name. Point `DEMO_HOST` and the other
  secrets at the new server.
- **Liana's own stack**: `docs/deployment.md` lists the parts (static admin app,
  the services, PostgreSQL, optional RabbitMQ) and what a production entry point
  needs. The demo logins are only for the demo; real login and organisations
  replace them.
- The Azure for Students credit lasts 12 months. Delete the `lianasurvey-demo`
  resource group to remove everything.
