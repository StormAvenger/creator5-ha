# GitHub usage must cost $0

The owner allows hosted GitHub features only when the billed outcome is $0. As of
2026-11-06 the owner has a GitHub Education account and approves GitHub Actions on
this public repository on that basis.

## Allowed

- GitHub Actions on **standard GitHub-hosted runners** (`ubuntu-latest`, etc.) in this
  public repository. GitHub's billing docs state these are free for public
  repositories and do not consume included usage.
- The workflows in `.github/workflows/`: HACS validation, hassfest, and the client,
  Home Assistant and frontend tests.
- Ordinary source control: commits, branches, issues, PRs, tags and source releases.

## Not allowed

- Larger runners (billed even for public repositories), or any runner size other
  than the standard ones.
- Uploading workflow artifacts or using Actions caches: GitHub's docs do not state
  that their storage is free for public repositories.
- Codespaces, paid Copilot features, paid security/marketplace apps, Git LFS or
  GitHub Packages storage, plan upgrades or trials that convert to paid plans.
- Adding a payment method, raising a budget or spending limit, or enabling any
  feature solely because an education benefit or free credit is advertised.
- Making the repository private: private-repository Actions minutes are metered.

If a change might create a cost and the docs don't say it's free, use a local
alternative or ask the owner first.

## Owner-side safeguards

- Settings → Actions → General: allow actions and reusable workflows, ideally
  restricted to GitHub-made actions plus `hacs/action` and `home-assistant/actions`.
- Billing → Budgets: keep any Actions budget at $0 with usage stopped at the limit.
  Without a payment method, GitHub blocks usage instead of charging.
- Check Billing → Usage occasionally; it should show $0 billed.

References:
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Managing GitHub Actions settings for a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
