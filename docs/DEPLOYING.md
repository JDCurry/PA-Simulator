# Publishing to Streamlit Community Cloud

Free, and the result is a URL your professors can open in a browser. No installation on
their side, no accounts, no student data to manage.

Total time, first run: about fifteen minutes.

---

## Before you start

You need a **GitHub account** and this project pushed to a GitHub repository. Streamlit
Community Cloud deploys from GitHub and nowhere else.

The repository can be **public or private** — Community Cloud handles both on the free
tier. Private is a reasonable default while you are still iterating.

---

## Step 1 — Confirm the repository is clean

From the project directory:

```bash
python -m pytest tests/ -q
```

All 83 tests should pass. Then confirm no real jurisdiction data is staged:

```bash
git status --short
```

You should see `data/scenarios/training_cascade_valley.json` and nothing else in
`data/scenarios/`. Files matching `*.local.json` are gitignored, and
`test_only_the_fictional_training_scenario_ships` fails the build if a real impact list
is ever committed.

---

## Step 2 — Push to GitHub

If the project is not yet a Git repository:

```bash
git init
```

```bash
git add -A
```

```bash
git commit -m "FEMA Public Assistance Workbench"
```

Create an empty repository on GitHub — do **not** initialise it with a README — then:

```bash
git remote add origin https://github.com/YOUR-USERNAME/pa-platform.git
```

```bash
git branch -M main
```

```bash
git push -u origin main
```

---

## Step 3 — Deploy

1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in three fields:
   - **Repository** — `YOUR-USERNAME/pa-platform`
   - **Branch** — `main`
   - **Main file path** — `app.py`
4. Optionally set a custom subdomain under **Advanced settings**. Something like
   `pa-workbench` gives you `pa-workbench.streamlit.app`, which is a much better link to
   put in an email than the default.
5. Click **Deploy**.

The first build takes two to five minutes while it installs from `requirements.txt`.
Watch the log pane; if it fails, the traceback is there.

Nothing else is needed. There are no secrets, no environment variables, and no database.

---

## Step 4 — Check it

Open the URL and verify:

- The app loads on the **Scenario** page, empty.
- **Load training scenario** in the sidebar populates it — the sidebar totals should
  read about $4.36M net eligible.
- **Compliance** shows roughly 20 blocking findings.
- **Training → Scorecard** shows about 33%, grade F.
- **Manual** renders the user manual, with PDF, Word, and Markdown download buttons.

If all five hold, it is working.

---

## Sharing it

Send the URL plus two sentences. Something like:

> This is a FEMA Public Assistance reimbursement simulator — a student plays the
> applicant after a disaster and assembles a reimbursement package. Click **Load
> training scenario** in the sidebar to start; the **Manual** page explains everything,
> and the **Training** tab has a suggested assignment structure.

Point them at the Manual page. It has a five-minute start, a full walkthrough from
failing to passing, and an instructor section.

---

## Things worth knowing

**Sessions are per-visitor and temporary.** Two people using the app at once do not see
each other's work. Closing the tab discards everything. This is deliberate — nothing is
stored server-side, so there is no jurisdiction's damage data sitting on Streamlit's
infrastructure. Tell students to use **Save working file** before they close the tab.

**Free-tier apps sleep.** After about a week without traffic the app goes to sleep, and
the next visitor sees a "waking up" screen for thirty seconds or so. It wakes
automatically. Nothing is lost. Visit the URL yourself before a class to pre-warm it.

**Resource limits.** The free tier gives about 1 GB of memory. This app is comfortably
inside that — it holds one scenario in memory and a 465-row CSV. A full class using it
at once is fine.

**Updating.** Push to `main` and Community Cloud redeploys automatically. Anyone with the
app open keeps their session until they reload.

**Editing the manual.** The Manual page reads `docs/USER_MANUAL.md` at run time, so
changing that file and pushing updates the in-app manual too. There is one copy.

---

## If something breaks

**Build fails on requirements.** Check `requirements.txt` is at the repository root and
that the Main file path is exactly `app.py`.

**`ModuleNotFoundError: No module named 'pa'`.** The Main file path is wrong, or `app.py`
is not at the repository root. Streamlit adds the script's directory to the import path,
so `app.py` must sit alongside `pa/` and `ui/`.

**The app loads but the equipment search returns nothing.** `data/equipment_rates_2025.csv`
did not get committed. Confirm with `git ls-files data/`.

**Manual page says the file is missing.** `docs/USER_MANUAL.md` was not committed.

**Manual page shows no PDF or Word download button.** Those buttons appear only when
`docs/PA_Workbench_User_Manual.pdf` and `.docx` are present. Build them with
`python tools/build_manual_docs.py` and commit the results — Streamlit Cloud has no
LaTeX or Node toolchain, so they cannot be generated at deploy time.

---

## Alternative: Render

`render.yaml` is included and the repository deploys as-is. Render's free tier also
sleeps when idle and is slower to wake than Streamlit Cloud. For handing a link to
professors, Streamlit Community Cloud is the simpler choice.
