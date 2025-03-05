# Variables
DOCKER_USERNAME ?= kapilldev
DOCKER_PWD ?= RqqrHRwE5uM
IMAGE_NAME = eventflows
TAG ?= latest
FULL_IMAGE_NAME = $(DOCKER_USERNAME)/$(IMAGE_NAME)


# ===========================================
# Docker Operations
# ===========================================

.PHONY: build-docker
build-docker:
	@echo "$(COLOR_YELLOW)$(EMOJI_DOCKER) Building Docker image...$(COLOR_RESET)"
	@docker build --no-cache -t $(FULL_IMAGE_NAME) .
	@echo "$(COLOR_GREEN)$(EMOJI_CHECK) Docker image built successfully!$(COLOR_RESET)"


# Tag and push to Docker Hub
.PHONY: docker-push
docker-push:
	@echo "$(COLOR_YELLOW)$(EMOJI_DOCKER) Logging into Docker Hub...$(COLOR_RESET)"
	@echo $(DOCKER_PWD) | docker login -u $(DOCKER_USERNAME) --password-stdin
	@echo "$(COLOR_YELLOW)$(EMOJI_DOCKER) Pushing image to Docker Hub...$(COLOR_RESET)"
	@docker push $(FULL_IMAGE_NAME):$(TAG)
	@echo "$(COLOR_GREEN)$(EMOJI_CHECK) Image pushed successfully!$(COLOR_RESET)"

.PHONY: local-build-run
local-build-run: 
	@echo "$(COLOR_YELLOW)$(EMOJI_DOCKER) Building and running Docker container...$(COLOR_RESET)"
	@docker build --no-cache -t $(FULL_IMAGE_NAME) .
	@docker run -d \
	-v ./instance:/instance \
	-p 8080:8080 \
	$(FULL_IMAGE_NAME)
	@echo "$(COLOR_GREEN)$(EMOJI_CHECK) Docker container built and running!$(COLOR_RESET)"


# Push to Docker Hub with all steps
.PHONY: deploy
deploy: 
	@echo "$(COLOR_YELLOW)$(EMOJI_DOCKER) Deploying (build and push)...$(COLOR_RESET)"
	@docker login -u $(DOCKER_USERNAME) -p $(DOCKER_PWD)
	@docker push $(FULL_IMAGE_NAME):$(TAG)
	@echo "$(COLOR_GREEN)$(EMOJI_CHECK) Deployment complete!$(COLOR_RESET)"

.PHONY: install run clean init-db migrate upgrade generate-dummy-events help

# Default python interpreter
PYTHON := python3
FLASK := FLASK_APP=webapp.migrations flask

# Help command
help:
	@echo "EventFlowAI Makefile commands:"
	@echo "  install              - Install dependencies"
	@echo "  run                  - Run the application"
	@echo "  clean                - Clean bytecode files"
	@echo "  init-db              - Initialize the database migrations"
	@echo "  migrate [msg=...]    - Create a new migration"
	@echo "  upgrade              - Apply migrations to the database"
	@echo "  generate-dummy-events [count=20] - Generate dummy events"

# Install dependencies
install:
	$(PYTHON) -m pip install -r requirements.txt

# Run the application
run:
	$(PYTHON) -m webapp.app

# Clean up bytecode files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete

# Database commands
init-db:
	$(FLASK) db init

migrate:
	@if [ -z "$(msg)" ]; then \
		read -p "Enter migration message: " message; \
		$(FLASK) db migrate -m "$$message"; \
	else \
		$(FLASK) db migrate -m "$(msg)"; \
	fi

upgrade:
	$(FLASK) db upgrade

# Generate dummy events
generate-dummy-events:
	@count=20; \
	if [ ! -z "$(count)" ]; then \
		count=$(count); \
	fi; \
	echo "Generating $$count dummy events..."; \
	$(PYTHON) -c "from webapp.app import app, generate_dummy_events; \
		with app.app_context(): \
			generate_dummy_events($$count)"