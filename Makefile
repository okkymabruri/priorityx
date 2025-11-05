# Version management for priorityx
# Semantic versioning: MAJOR.MINOR.PATCH
# - patch: bug fixes (0.1.1 -> 0.1.2)
# - minor: new features, backward compatible (0.1.2 -> 0.2.0)
# - major: breaking changes (0.2.0 -> 1.0.0)

.PHONY: release release-patch release-minor release-major test

# Release patch version
release-patch:
	@uv run python scripts/version.py release

# Release minor version
release-minor:
	@uv run python scripts/version.py release --minor

# Release major version
release-major:
	@uv run python scripts/version.py release --major

# Release specific version (e.g., make release VERSION=0.2.0)
release:
	@test -n "$(VERSION)" || (echo "Error: Set VERSION=x.y.z" && exit 1)
	@uv run python scripts/version.py release $(VERSION)

# Run tests
test:
	@uv run pytest tests/
