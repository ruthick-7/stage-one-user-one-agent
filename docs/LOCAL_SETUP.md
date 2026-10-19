# How I run the project locally

This is my Windows/PowerShell setup guide, including the folder layout and commands I need. The website also runs on macOS and Linux. It needs **Python 3.10 or newer** and a current browser. Everything required at runtime is in Python's standard library, so there is no npm or pip setup step.

## 1. Get my latest project

Open <https://github.com/ruthick-7/stage-assessment>.

- If you downloaded a ZIP previously: choose **Code → Download ZIP**, then extract the updated project into a new folder. Copy your existing `data_pack` folder into that new project folder if you want to run new replays.
- If you cloned with Git: open a terminal inside the repository and run `git pull origin main`.

Do not replace your original data pack or delete old replay results while updating. Website accounts and private runs live in `.local/web/`; preserve that directory if updating an existing website installation.

## 2. Open the project folder in a terminal

Open the extracted folder in VS Code, then choose **Terminal → New Terminal**. You should see `serve.py`, `run.py`, `web/`, `src/`, and `sample_run/` in that folder.

For the Windows folder I used earlier, the command is:

```powershell
cd "D:\Downloads\codex-stage\stage-assessment"
dir
```

If the new ZIP extracted as `stage-assessment-main`, use that actual folder path instead.

## 3. Check Python

```powershell
python --version
```

The Python 3.13 installation I used for the earlier Windows run meets the requirement. If Windows recognizes `py` instead of `python`, use `py` in the commands below. If neither works, install Python from <https://www.python.org/downloads/> and enable **Add Python to PATH**, then reopen the terminal.

A virtual environment is optional because there are no third-party runtime dependencies. There is no need to change PowerShell execution policy or run an activation script.

## 4. Start the website

From the project folder:

```powershell
python serve.py
```

The terminal prints:

```text
STAGE website: http://127.0.0.1:8000
Press Ctrl+C to stop. Accounts and private runs are stored locally.
```

Keep this terminal open. Open **http://127.0.0.1:8000** in Chrome, Edge, or Firefox. Do not double-click `web/index.html`: the sign-in and dashboard APIs require the Python server.

## 5. Create your local account

1. Select **Create account**.
2. Enter your name and an email address.
3. Choose a password of 10–128 characters.
4. Select **Create account**. You will enter the dashboard.

This account belongs to this local development website, not the STAGE streaming service. There is no preconfigured account, verification email, Google login, or email-based password recovery. Passwords are stored as salted hashes, not plaintext. Use your own account details; test credentials are not demo logins.

On future visits, select **Sign in**. A signed-in session survives a page refresh and server restart until it expires or is revoked.

## 6. Explore the included sample

You can do this **without extracting the data pack**:

| Page | What you can do |
|---|---|
| Overview | See decision counts, action mix, hourly activity, goal judgments and policy checks |
| Viewers | Search by viewer ID, filter randomized arms, and inspect facts, decisions, checks and outcomes |
| Decisions | Search decisions and filter home pages versus abstentions |
| Experiments | Inspect randomized baseline-goal results, missing follow-up and uncertainty bounds |
| Reports | Read or download the final, impact, latency, quality, audit and simulator reports |
| Replay studio | Launch a new local replay, watch its status, cancel it, and open completed results |
| Account settings | Edit your name, change your password, revoke other sessions and sign out |

I use actual result files for the dashboard values. The sample is historical synthetic assignment data; it is not live production traffic. Times displayed in the workspace use IST.

## 7. Add the data pack for new replays

Extract the original assignment ZIP. Its enclosing folder is `one_user_one_agent_pack`. Rename that **inner** folder to `data_pack`, then place it beside `serve.py`:

```text
stage-assessment/
  serve.py
  run.py
  web/
    index.html
    style.css
    app.js
  src/
  sample_run/
  data_pack/
    README.md
    data/
      catalogue.csv
      episodes.csv
      events.jsonl
      profiles_snapshot.csv
    config/
    replay/
    pilot/
    simulator/
```

Check the path:

```powershell
Test-Path .\data_pack\data\catalogue.csv
```

It must print `True`. Avoid `data_pack\one_user_one_agent_pack\data\...` nesting.

Refresh the website after adding the pack. If your pack is elsewhere, stop the server and restart with:

```powershell
python serve.py --pack "D:\path\to\one_user_one_agent_pack"
```

## 8. Start a replay from the website

1. Open **Replay studio**.
2. Enter a simulator seed, such as `my-first-run`.
3. Select **Start replay**.
4. The run progresses from queued to running, then completed or failed. It may take longer on your PC than on the validation machine.
5. Select **Open** when completed. The dashboard, viewer explorer, experiments and reports now show that run.
6. Use the run selector in the header to switch back to **Included sample**.

A run is marked completed only after the replay **and independent artifact audit** succeed. One replay runs at a time in this website instance. Generated runs are private to their local account; other accounts can view the shared sample but not your generated runs. Cancelled or failed partial results are not selectable as completed runs.

## 9. Run checks from another terminal

Leave the website terminal running and open a second VS Code terminal in the project folder:

```powershell
python -m unittest discover -s tests -v
```

For the original CLI workflow:

```powershell
python run.py --pack data_pack --out practice_run_website
python audit_run.py --pack data_pack --run practice_run_website
```

Use a new output name each time. The website manages its own output directories; manually created CLI outputs do not automatically appear in the run selector.

## 10. Stop and restart

Press **Ctrl+C** in the website terminal. Start again with `python serve.py` when needed.

Account and run metadata persist in `.local/web/accounts.sqlite3`; private outputs and logs are in `.local/web/runs/`. These are excluded from Git. Stop the server before backing up the entire `.local/web/` directory. Do not delete just the database to fix a password: that also removes account-to-run ownership metadata.

An interrupted replay is marked failed when the website next starts. Start a fresh run rather than presenting partial output as completed evidence.

## Troubleshooting

**“python is not recognized”**

Try `py --version`, or install Python and reopen the terminal.

**“can't open file serve.py”**

You are in the wrong folder or have the older project version. Run `dir` and locate the updated folder containing `serve.py`.

**“Address already in use” / port 8000 unavailable**

Stop your previous website terminal, or use another port:

```powershell
python serve.py --port 8001
```

Then open **http://127.0.0.1:8001**. Run only one website instance per account-data directory.

**“Assignment pack required”**

The sample still works. New replays need the original pack and correct nesting. Recheck `Test-Path` above, then refresh the browser. If using a different pack path, restart with `--pack`.

**A replay failed**

Check the terminal and the corresponding `.local/web/runs/<account-id>/<run-id>.log` file. Correct the prerequisite and start a new replay. Do not mark the job completed manually.

**“Too many attempts”**

Wait one minute before trying to sign in again.

**Session verification failed**

Refresh the page. Use the same address consistently; `localhost` and `127.0.0.1` use separate browser cookie storage.

**Forgotten password**

There is no email reset service. You can create another local account; existing private runs remain associated with the original account. Keep an account-data backup if those results matter.

## What this local setup covers

I run this website on my computer's loopback address for development and assessment. To publish it on the internet, I would need a production web server, HTTPS, deployment-specific authentication and job infrastructure. The current version lets me explore synthetic replay results; it does not stream video.
