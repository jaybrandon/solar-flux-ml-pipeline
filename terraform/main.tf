terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.29.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

resource "google_artifact_registry_repository" "docker-repo" {
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
  name          = "solar_flare_offline_fs"
  location      = var.location
  force_destroy = true
  versioning { enabled = true }

  lifecycle_rule {
    condition { age = 1 }
    action { type = "AbortIncompleteMultipartUpload" }
  }
}

resource "google_storage_bucket" "online_feature_store" {
  name          = "solar_flare_online_fs"
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