# Release Process for stella_workflow

This document outlines the steps to release the stella_workflow package to PyPI using GitHub Actions.

## Prerequisites

1. **PyPI Account**: You need a PyPI account to publish packages.
2. **GitHub Repository**: The code should be hosted on GitHub.
3. **GitHub Secrets**: Set up the following secrets in your GitHub repository:
   - `PYPI_USERNAME`: Your PyPI username
   - `PYPI_PASSWORD`: Your PyPI password or token (recommended)

## Release Process

### 1. Update Package Version

Update the version in `pyproject.toml`:

```toml
[tool.poetry]
name = "stella-workflow"
version = "x.y.z"  # Update this version
```

### 2. Update Changelog

Make sure to update the `CHANGELOG.md` file with the changes in the new version.

### 3. Commit and Push Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Bump version to x.y.z"
git push origin main
```

### 4. Create a GitHub Release

1. Go to your GitHub repository
2. Click on "Releases" in the right sidebar
3. Click "Create a new release"
4. Enter the tag version (e.g., `v1.0.0`)
5. Enter a release title (e.g., "v1.0.0 - Initial Release")
6. Add release notes (you can copy from the CHANGELOG)
7. Click "Publish release"

### 5. Monitor GitHub Actions

Once you publish the release, GitHub Actions will automatically:
1. Build the package
2. Upload it to PyPI

You can monitor the progress in the "Actions" tab of your GitHub repository.

## Manual Release (if needed)

If you need to release manually:

```bash
# Install dependencies
pip install poetry build twine

# Build the package
poetry build

# Upload to PyPI
twine upload dist/*
```

## Testing the Release

After the release, you can verify it by installing from PyPI:

```bash
pip install stella-workflow
# or for a specific version
pip install stella-workflow==x.y.z
```

## Troubleshooting

### Common Issues

1. **Authentication Failure**: Check your PyPI credentials in GitHub secrets.
2. **Version Conflict**: Ensure you're not trying to upload a version that already exists on PyPI.
3. **Build Failure**: Check the GitHub Actions logs for details.

### GitHub Actions Logs

If the release fails, check the GitHub Actions logs:
1. Go to your GitHub repository
2. Click on the "Actions" tab
3. Click on the failed workflow
4. Examine the logs for error messages

## Development Workflow

For ongoing development:

1. Create feature branches from `develop`
2. Make changes and submit PRs to `develop`
3. Merge `develop` into `main` when ready for a release
4. Tag and release from `main`

This ensures that the `main` branch always represents the latest stable release. 