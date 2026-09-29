.PHONY: test health stats curate visualize visualize-build clean

test:
	uv run pytest

health:
	uv run spec-ops health

stats:
	uv run spec-ops stats

curate:
	uv run spec-ops curate

visualize:
	uv run spec-ops visualizer --serve

visualize-build:
	uv run spec-ops visualizer --build dist/visualizer.html

clean:
	rm -rf dist/ site/ .worktrees/ .pytest_cache/
