"""Expose the hidden hooks directory to root unittest discovery."""


def load_tests(loader, tests, pattern):
    return loader.discover(".githooks", pattern="test_*.py", top_level_dir=".githooks")
