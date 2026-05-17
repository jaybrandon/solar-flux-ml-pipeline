terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.29.0"
    }
    github = {
      source  = "integrations/github"
      version = "6.12.1"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

provider "github" {
  owner = var.github_repo_owner
  token = var.github_token
}

resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.location
  repository_id = "docker"
  description   = "main docker repository"
  format        = "DOCKER"

  docker_config {
    immutable_tags = true
  }

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-minimum-versions"
    action = "KEEP"
    most_recent_versions {
      package_name_prefixes = ["backfill", "feature"]
      keep_count            = 3
    }
  }

  cleanup_policies {
    id     = "delete-older-than-7-days"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "7d"
    }
  }

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state = "UNTAGGED"
    }
  }
}

resource "google_storage_bucket" "offline_feature_store" {
  name          = "${var.project}_offline_fs"
  location      = var.location
  force_destroy = true
  versioning { enabled = true }

  lifecycle_rule {
    condition { age = 1 }
    action { type = "AbortIncompleteMultipartUpload" }
  }
}

resource "google_storage_bucket" "online_feature_store" {
  name          = "${var.project}_online_fs"
  location      = var.location
  force_destroy = true

  lifecycle_rule {
    condition { age = 3 }
    action { type = "Delete" }
  }

  lifecycle_rule {
    condition { age = 1 }
    action { type = "AbortIncompleteMultipartUpload" }
  }
}

resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-ip"
}

resource "google_iam_workload_identity_pool_provider" "gh_actions_prvdr" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "gh-actions-prvdr"
  display_name                       = "GitHub Actions"
  description                        = "GitHub Actions identity pool provider"

  attribute_condition = <<EOT
    assertion.repository_owner_id == "${var.github_repo_owner_id}" &&
    attribute.repository == "${var.github_repo_owner}/${var.github_repo_name}" &&
    assertion.ref == "refs/heads/main" &&
    assertion.ref_type == "branch"
EOT
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.aud"        = "assertion.aud"
    "attribute.repository" = "assertion.repository"
    "attribute.workflow"   = "assertion.workflow"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "backfill_sa" {
  account_id   = "backfill-sa"
  display_name = "Backfill pipeline Account"
}

resource "google_service_account_iam_member" "backfill_sa_oidc" {
  service_account_id = google_service_account.backfill_sa.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.workflow/${var.backfill_workflow_name}"
}

resource "google_storage_bucket_iam_member" "backfill_sa_bucket" {
  bucket = google_storage_bucket.offline_feature_store.name
  role   = "roles/storage.objectAdmin"

  member = "serviceAccount:${google_service_account.backfill_sa.email}"
}

resource "google_service_account" "batch_sa" {
  account_id   = "batch-sa"
  display_name = "Batch pipeline Account"
}

resource "google_service_account_iam_member" "batch_sa_oidc" {
  service_account_id = google_service_account.batch_sa.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.workflow/${var.batch_workflow_name}"
}

resource "google_storage_bucket_iam_member" "batch_sa_offline_bucket" {
  bucket = google_storage_bucket.offline_feature_store.name
  role   = "roles/storage.objectAdmin"

  member = "serviceAccount:${google_service_account.batch_sa.email}"
}

resource "google_storage_bucket_iam_member" "batch_sa_online_bucket" {
  bucket = google_storage_bucket.online_feature_store.name
  role   = "roles/storage.objectAdmin"

  member = "serviceAccount:${google_service_account.batch_sa.email}"
}

resource "google_service_account" "train_sa" {
  account_id   = "train-sa"
  display_name = "Training pipeline Account"
}

resource "google_service_account_iam_member" "train_sa_oidc" {
  service_account_id = google_service_account.train_sa.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.workflow/${var.train_workflow_name}"
}

resource "google_storage_bucket_iam_member" "train_sa_offline_bucket" {
  bucket = google_storage_bucket.offline_feature_store.name
  role   = "roles/storage.objectAdmin"

  member = "serviceAccount:${google_service_account.train_sa.email}"
}

resource "github_actions_variable" "wif_provider_name" {
  repository    = var.github_repo_name
  variable_name = "GCP_WORKLOAD_IDENTITY_PROVIDER"
  value         = google_iam_workload_identity_pool_provider.gh_actions_prvdr.name
}

resource "github_actions_variable" "backfill_sa_email" {
  repository    = var.github_repo_name
  variable_name = "GCP_BACKFILL_SERVICE_ACCOUNT"
  value         = google_service_account.backfill_sa.email
}

resource "github_actions_variable" "batch_sa_email" {
  repository    = var.github_repo_name
  variable_name = "GCP_BATCH_SERVICE_ACCOUNT"
  value         = google_service_account.batch_sa.email
}

resource "github_actions_variable" "train_sa_email" {
  repository    = var.github_repo_name
  variable_name = "GCP_TRAIN_SERVICE_ACCOUNT"
  value         = google_service_account.train_sa.email
}

resource "github_actions_variable" "offline_fs_bucket" {
  repository    = var.github_repo_name
  variable_name = "GCP_OFFLINE_FEATURE_STORE_BUCKET"
  value         = google_storage_bucket.offline_feature_store.url
}

resource "github_actions_variable" "online_fs_bucket" {
  repository    = var.github_repo_name
  variable_name = "GCP_ONLINE_FEATURE_STORE_BUCKET"
  value         = google_storage_bucket.online_feature_store.url
}

resource "github_actions_variable" "wandb_entity" {
  repository    = var.github_repo_name
  variable_name = "WANDB_ENTITY"
  value         = var.wandb_entity
}

resource "github_actions_variable" "wandb_project" {
  repository    = var.github_repo_name
  variable_name = "WANDB_PROJECT"
  value         = var.wandb_project
}

resource "github_actions_secret" "wandb_api_key" {
  repository  = var.github_repo_name
  secret_name = "WANDB_API_KEY"
  value       = var.wandb_api_key
}