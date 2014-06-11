all: clean vendor

clean:
	@# Delete vendored items
	find . -maxdepth 1 -mindepth 1 -type d -exec rm -rf {} \;

vendor:
	@# Install vendored libraries
	pip install -t . -r vendor.txt

	@# Cleanup .egg-info directories
	rm -rf *.egg-info

	rm -rf keyring/tests
	rm -rf win32ctypes/tests
	rm -rf pyyaml/tests
	rm -f _yaml*
	rm -rf sqlite_cache/tests
