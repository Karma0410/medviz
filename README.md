# MedViz

## Git Workflow

```
Issue → Branch (from issue) → Commits → Merge Request (from issue) → Review → Merge into dev
```

---

### Step 1 — Create an Issue

Go to **Issues → New Issue**. Add a title, description, and relevant labels. Submit.

---

### Step 2 — Create a Branch from the Issue

On the issue page, click **Create merge request / pull request**.  
This automatically creates and names a branch correctly (e.g. `42-user-profile`) and links it to the issue and a merge request and will close it on merge.

- Set target branch to `dev` never `main`
- Add a short description of what was done
- Mark as **Draft** if not ready yet

```bash
git fetch origin
git checkout 42-user-profile
```

> Always branch off `dev`. Make sure to select it as the source branch in the dialog.

---

### Step 3 — Commit & Push

```bash
git add .
git commit -m "feat: add user profile page (#42)"
git push origin 42-user-profile
```

---

### Step 4 — Request a Review

Assign **1 or 2 reviewers** in the MR sidebar. Address all comments, then re-request review if changes were made.

---

### Step 5 — Merge

Once approved:

1. Rebase on `dev` if needed: `git rebase origin/dev`
2. Click **Squash and merge**
3. Delete the branch

---

### Branch Protection

| Branch | Direct push | Required to merge |
|--------|-------------|-------------------|
| `main` | Nope | MR from `dev` + 2 approvals |
| `dev`  | Nope | MR from feature branch + 1 approval |