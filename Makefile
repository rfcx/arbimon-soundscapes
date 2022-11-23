# The binary to build (just the basename).
MODULE := soundscapes

# Where to push the docker image.
REGISTRY ?= 887044485231.dkr.ecr.eu-west-1.amazonaws.com

IMAGE := $(REGISTRY)/$(MODULE)

# This version-strategy uses git tags to set the version string
TAG := $(shell git describe --tags --always --dirty)

BLUE='\033[0;34m'
NC='\033[0m' # No Color

run:
	@python -m $(MODULE) $(ARGS)

test:
	@pytest

lint:
	@echo "\n${BLUE}Running Flake8 against source and test files...${NC}\n"
	@flake8
	@echo "\n${BLUE}Running Bandit against source files...${NC}\n"
	@bandit -r -c bandit.yaml $(MODULE)

lint-fix:
	@autoflake8 --in-place -r **/*.py

build-dev:
	@echo "\n${BLUE}Building development image with labels:\n"
	@echo "name: $(MODULE)"
	@echo "version: $(TAG)${NC}\n"
	@docker build -t $(MODULE):$(TAG) -f build/Dockerfile .

# Example: make shell CMD="-c 'date > datefile'"
shell: build
	@echo "\n${BLUE}Launching a shell in the containerized build environment...${NC}\n"
		@docker run                                                 \
			-ti                                                     \
			--rm                                                    \
			--entrypoint /bin/bash                                  \
			-v ${PWD}:/app                                          \
			-u $$(id -u):$$(id -g)                                  \
			$(MODULE):$(TAG)										\
			$(CMD)

version:
	@echo $(TAG)

clean:
	rm -rf .pytest_cache .coverage .pytest_cache coverage.xml

docker-clean:
	@docker system prune -f --filter "label=name=$(MODULE)"