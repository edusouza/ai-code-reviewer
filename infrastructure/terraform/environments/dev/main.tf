module "network" {
  source = "../../modules/network"

  project_id         = var.project_id
  region             = var.region
  environment        = var.environment
  subnet_cidr        = var.subnet_cidr
  vpc_connector_cidr = var.vpc_connector_cidr
}

module "iam" {
  source = "../../modules/iam"

  project_id  = var.project_id
  environment = var.environment
}

module "core" {
  source = "../../modules/core"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment

  core_service_account_email = module.iam.core_service_account_email
  vpc_connector_name         = module.network.vpc_connector_name

  api_image    = var.api_image
  worker_image = var.worker_image
  webhook_image = var.webhook_image

  api_cpu_limit    = var.api_cpu_limit
  api_memory_limit = var.api_memory_limit
  min_instances    = var.min_instances
  max_instances    = var.max_instances

  worker_cpu_limit    = var.worker_cpu_limit
  worker_memory_limit = var.worker_memory_limit
  worker_min_instances = var.worker_min_instances
  worker_max_instances = var.worker_max_instances

  langfuse_host = module.langfuse.langfuse_web_url

  github_token    = var.github_token
  openai_api_key  = var.openai_api_key
  webhook_secret  = var.webhook_secret
  langfuse_public_key = var.langfuse_public_key
  langfuse_secret_key = var.langfuse_secret_key

  depends_on = [module.network, module.iam]
}

module "langfuse" {
  source = "../../modules/langfuse"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment

  vpc_id                      = module.network.vpc_id
  vpc_connector_name          = module.network.vpc_connector_name
  langfuse_service_account_email = module.iam.langfuse_service_account_email

  db_tier         = var.langfuse_db_tier
  nextauth_secret = var.nextauth_secret
  langfuse_salt   = var.langfuse_salt

  depends_on = [module.network, module.iam]
}

module "observability" {
  source = "../../modules/observability"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment

  observability_service_account_email = module.iam.observability_service_account_email
  api_host                            = module.core.api_blue_url
  alert_email                         = var.alert_email
  domain                              = var.domain

  depends_on = [module.core, module.iam]
}
