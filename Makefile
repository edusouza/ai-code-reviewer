# Blue-Green Deployment Makefile
# Usage: make <command> ENV=<environment>

ENV ?= dev
SCRIPT_DIR := scripts
TERRAFORM_DIR := terraform

.PHONY: help deploy canary promote rollback status health check clean

help: ## Show this help message
	@echo "Blue-Green Deployment Commands"
	@echo "=============================="
	@echo ""
	@echo "Usage: make <command> ENV=<environment>"
	@echo ""
	@echo "Environments: dev, staging, prod"
	@echo ""
	@echo "Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make deploy ENV=prod     # Deploy to production"
	@echo "  make canary ENV=prod     # Start canary deployment"
	@echo "  make status ENV=prod     # Check deployment status"

deploy: ## Deploy new version (creates green environment)
	@echo "🚀 Deploying to $(ENV)..."
	@chmod +x $(SCRIPT_DIR)/deploy.sh
	@$(SCRIPT_DIR)/deploy.sh $(ENV) deploy

canary: ## Start canary deployment (10% traffic to green)
	@echo "🐤 Starting canary deployment to $(ENV)..."
	@chmod +x $(SCRIPT_DIR)/deploy.sh
	@$(SCRIPT_DIR)/deploy.sh $(ENV) canary

promote: ## Promote green to 100% traffic
	@echo "⬆️  Promoting to 100% in $(ENV)..."
	@chmod +x $(SCRIPT_DIR)/deploy.sh
	@$(SCRIPT_DIR)/deploy.sh $(ENV) promote

rollback: ## Emergency rollback to blue
	@echo "🚨 Rolling back in $(ENV)..."
	@chmod +x $(SCRIPT_DIR)/deploy.sh
	@$(SCRIPT_DIR)/deploy.sh $(ENV) rollback

status: ## Check deployment status
	@echo "📊 Checking status for $(ENV)..."
	@if [ -f .green_url ]; then \
		echo "GREEN environment active: $$(cat .green_url)"; \
	else \
		echo "No GREEN deployment in progress - BLUE is 100%"; \
	fi
	@cd $(TERRAFORM_DIR) && terraform workspace select $(ENV) 2>/dev/null && terraform output 2>/dev/null || echo "Terraform outputs not available"

health: ## Run health checks
	@echo "🏥 Running health checks..."
	@if [ -f .green_url ]; then \
		$(SCRIPT_DIR)/health_check.sh "$$(cat .green_url)"; \
	else \
		echo "No GREEN URL found. Deploy first or provide URL: make health URL=https://..."; \
	fi

monitor: ## Monitor deployment (5 minutes)
	@echo "📈 Monitoring $(ENV) for 5 minutes..."
	@chmod +x $(SCRIPT_DIR)/monitor.sh
	@$(SCRIPT_DIR)/monitor.sh $(ENV) 300

monitor-10m: ## Monitor deployment (10 minutes)
	@echo "📈 Monitoring $(ENV) for 10 minutes..."
	@chmod +x $(SCRIPT_DIR)/monitor.sh
	@$(SCRIPT_DIR)/monitor.sh $(ENV) 600

check: ## Run pre-deployment checks
	@echo "🔍 Running pre-deployment checks..."
	@command -v gcloud >/dev/null 2>&1 || (echo "❌ gcloud not found" && exit 1)
	@command -v terraform >/dev/null 2>&1 || (echo "❌ terraform not found" && exit 1)
	@echo "✅ gcloud installed"
	@echo "✅ terraform installed"
	@if [ -f config/$(ENV).env ]; then \
		echo "✅ Config file exists for $(ENV)"; \
	else \
		echo "❌ Config file missing: config/$(ENV).env"; \
		exit 1; \
	fi
	@echo "✅ All checks passed!"

init: ## Initialize terraform and dependencies
	@echo "🔧 Initializing..."
	@cd $(TERRAFORM_DIR) && terraform init
	@chmod +x $(SCRIPT_DIR)/*.sh
	@mkdir -p logs

plan: ## Show terraform plan
	@echo "📋 Showing plan for $(ENV)..."
	@cd $(TERRAFORM_DIR) && terraform workspace select $(ENV) 2>/dev/null || terraform workspace new $(ENV)
	@cd $(TERRAFORM_DIR) && terraform plan

clean: ## Clean up temporary files and logs
	@echo "🧹 Cleaning up..."
	@rm -f .green_url
	@rm -f logs/deploy_*.log
	@echo "✅ Cleanup complete"

logs: ## Show recent deployment logs
	@echo "📋 Recent deployment logs:"
	@ls -1t logs/deploy_*.log 2>/dev/null | head -5 || echo "No logs found"

full-deploy: check deploy canary promote ## Full deployment: check → deploy → canary → promote
	@echo "✅ Full deployment complete!"

.DEFAULT_GOAL := help
