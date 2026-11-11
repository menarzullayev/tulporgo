# Running TulporGo on the owner's PC (decision 70)

Until TulporGo makes a profit it runs on Saidakbar aka's PC in Uzbekistan (no VPS). A university server is the later
candidate and will be measured first. The stack is the same Docker Compose project as in `docs/DEPLOY.md`; only the
way it reaches the internet changes: a **Cloudflare Tunnel** instead of open ports 80/443.

Owner = Saidakbar aka (money, accounts, registrar, passwords). Claude = everything else, with a check after each step.

## Measured on 2026-11-11

| What | Value | Meaning |
|---|---|---|
| CPU / RAM | i7-13700F (16 cores, 24 threads), 31.8 GB | plenty |
| Docker | 29.8.2; WSL VM capped at 10 GB / 6 CPUs (`~/.wslconfig`, for the RankWant runner) | containers already use ~4.6 GB of it (RankWant, hisobox, cpstands, others) — TulporGo has to fit in the rest |
| Disk free | C: 48 GB, D: 26 GB | enough for the database and one local dump (decision 58) |
| Ports 80 / 443 on the host | free | not needed anyway: the tunnel publishes nothing |
| Public IP | one address seen from outside | may change; the tunnel does not depend on it |
| Power | no UPS; sleep on AC is off; BIOS powers on when power returns (owner, decision 71) | office cuts are rare and short (≤ ~10 min); the PC comes back by itself |
| After a reboot | Docker Desktop starts **only after a user logs in** (Run key) | fixed by auto-logon + lock (decision 71, below) |
| Coming-soon stub | Task Scheduler `TulporGo coming-soon bot`, running | must stop before the real bot starts (one `getUpdates` consumer per token) |
| DNS | NS `ns1/ns2.eskiz.uz`; no apex A; MX ×3 Zoho, SPF, Zoho verification TXT, DKIM `zmail._domainkey`, DMARC `p=reject`, CAA `letsencrypt.org`, `www` CNAME | all of these must exist at Cloudflare **before** the nameservers change, or mail breaks |

Checked by Claude: `deploy/docker-compose.pc.yml` merges cleanly (proxy publishes no port, `tunnel` service added),
a missing `TULPORGO_TUNNEL_TOKEN` stops the config with a clear error, `COMPOSE_FILE` in `deploy/.env` picks up the
override on Windows, and Caddy 2.10 with `TULPORGO_DOMAIN=:80` listens on plain HTTP `:80`.

## How it fits together

```
user ── HTTPS ──> Cloudflare (tulporgo.uz) ── tunnel ──> tunnel container ── HTTP ──> proxy (Caddy :80)
                                                                                   ├─ /api, /legal → api:8000
                                                                                   └─ /app → Mini App files
bot, userbot ── outbound only ──> Telegram;  offsite ── outbound ──> Cloudflare R2
```

Nothing listens on the PC's network ports. The database, backups and encrypted sessions stay on the PC (decisions 43,
67, 70).

## Steps

| # | Step | Who | Done when |
|---|---|---|---|
| 1 | **Production checkout** separate from the dev folder: `git clone https://github.com/menarzullayev/tulporgo D:\tulporgo-prod` (`deploy.sh` checks out a commit — it must never run in `D:\Linux\coding\taxi-bot`) | Claude | `git -C D:\tulporgo-prod log -1` = `origin/main` |
| 2 | **`deploy/.env`** in the production checkout from `.env.example`: bot token, Telegram app, login secret, R2 (from `.secrets/*.env`), operator name/address (`.secrets/operator.env`), documents storage chat (`.secrets/telegram_storage.env`), `COMPOSE_FILE=docker-compose.yml;docker-compose.pc.yml`, `TULPORGO_DOMAIN=tulporgo.uz`. Three new keys are generated (userbot, documents, backup) | Claude generates; **owner** stores the three keys in a password manager | `docker compose config` passes; `secret_scan` 0 |
| 3 | **Add tulporgo.uz to the TulporGo Cloudflare account** (Free plan). Cloudflare imports the records; Claude compares them with the table above and adds any that are missing (MX, SPF, Zoho TXT, DKIM, DMARC, CAA, `www`) | **owner** clicks "Add a domain"; Claude checks | every record from the table is in the Cloudflare zone |
| 4 | **Tunnel**: Cloudflare → Networks → Tunnels → Create (cloudflared). Public hostnames `tulporgo.uz` and `www.tulporgo.uz` → `http://proxy:80`. The token goes into `.secrets/tunnel.env` (owner writes it, Claude checks without printing) and into `deploy/.env` as `TULPORGO_TUNNEL_TOKEN` | **owner** creates; Claude fills the form if asked and checks | token present, tunnel listed |
| 5 | **Nameservers**: Eskiz panel → tulporgo.uz → DNS servers → the two Cloudflare NS | **owner** | `whois` and `dig NS` show Cloudflare; can take up to 24 h |
| 6 | **Mail check** after the switch: MX/SPF/DKIM/DMARC answered by Cloudflare; a test mail in and out of info@tulporgo.uz | Claude checks DNS; **owner** sends the test mail | mail works both ways |
| 7 | **Start**: stop the coming-soon task, then `./scripts/deploy.sh` in Git Bash from `D:\tulporgo-prod\deploy` (backup → start → health → `https://tulporgo.uz/api/health`) | Claude (stopping the stub is announced first) | `deployed.log` has the commit; health 200 through Cloudflare |
| 8 | **Live checks**: `/legal/terms` and `/legal/privacy` (uz/ru, operator filled in), Mini App `/app/`, bot `/start`, Login with Telegram end to end, one manual backup + the encrypted R2 copy | Claude; **owner** does the Telegram login and taps through the bot | all pass |
| 9 | **BotFather**: Mini App URL `https://tulporgo.uz/app/` and the menu button | Claude via Bot API where possible; **owner** in BotFather for the rest | `getMe.has_main_web_app=true` |
| 10 | **Auto-logon**: Sysinternals Autologon (official, keeps the password encrypted) → Enable; then one test reboot | **owner** (password); Claude checks the lock task and that the stack came back | `lock-after-autologon.ps1 -DryRun` says `autologon=True`; containers up after reboot |

Rollback at any step: `docker compose down` in `D:\tulporgo-prod\deploy` (volumes are kept), start the coming-soon task
again. Before step 5 nothing public changes; DNS can be pointed back to Eskiz at the registrar.

## Keeping it running on a PC

| Risk | What helps | Cost |
|---|---|---|
| Power cut | BIOS powers on when power returns (on); no UPS — office cuts are short (decision 71) | accepted |
| Reboot (Windows Update, power) leaves everything down until login | Windows auto-logon + `deploy/windows/lock-after-autologon.ps1` (Task Scheduler "TulporGo lock after auto-logon") locks the screen at once; it locks only when AutoAdminLogon=1 and uptime < 5 min | Windows Update settings unchanged: a daytime update reboot means a few minutes down, then everything returns |
| Internet cut | nothing on the PC side; the tunnel reconnects by itself | — |
| Docker VM memory (10 GB shared) | measure TulporGo's real use after step 7; raise `memory=` in `.wslconfig` only if needed (needs `wsl --shutdown`, which restarts every project's containers) | a short stop for all projects |
| Disk | one local dump + R2 copy (decision 58); check free space monthly | — |
| R2 token IP filter | **not** set on a PC: the home IP can change and backups would fail | — |

## When the university server comes

Measure it first (CPU, RAM, disk, uptime, who has access, whether outbound HTTPS and Telegram are allowed, whether
the data stays in Uzbekistan). If it fits: same production checkout, same `deploy/.env` (move the three keys), restore
the latest dump there (`docs/DEPLOY.md`, Restore), point the tunnel at the new machine — DNS does not change.
