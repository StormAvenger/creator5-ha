# No paid GitHub usage

The user requires that our work incur no GitHub charges. Future student benefits
can be considered only after activation and verification that use remains free,
including expiry and limits. They do not authorize overages or paid features.

On 2026-10-06, repository Settings → Actions → General was set to **Disable actions**.
GitHub confirmed the policy update. It prevents workflow runs on every branch,
including main. The development branch also archives the former workflow under
docs/reference; that location cannot trigger Actions.

Use the existing Mac/Ubuntu environments for tests, lint, typing and builds.
Keep GitHub for ordinary source control and review. Do not start hosted compute,
Codespaces, paid Copilot/security/marketplace features, converting trials, upgrades,
or potentially metered LFS/package storage. Do not raise budgets or add payment
information. Verify any future education-covered feature and its no-overage controls
with the user before enabling it; do not enable features automatically on a date.

Earlier CI results are historical evidence, not authorization for future hosted
test runs. Included usage and billable spend differ. Account-specific balances
and billing screenshots stay outside source control.

References:
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Disabling repository Actions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
