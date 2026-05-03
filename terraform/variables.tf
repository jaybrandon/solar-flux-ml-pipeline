variable "project" {
  description = "The Google Cloud Project ID"
}

variable "github_repo_name" {
  description = "The GitHub repository name"
  type        = string
}

variable "github_repo_owner" {
  description = "The GitHub repository owner"
  type        = string
}

variable "github_repo_owner_id" {
  description = "The GitHub repository owner id that is allowed to assume the gcloud service account."
  type        = number
}

variable "github_token" {
  description = "GitHub personal access token with access to the repository and variable write permission"
  type        = string
}

variable "backfill_workflow_name" {
  description = "Name of the GitHub Actions workflow allowed to assume the gcp role"
  type        = string
  default     = "Feature Backfill Pipeline"
}

variable "batch_workflow_name" {
  description = "Name of the GitHub Actions workflow allowed to assume the gcp role"
  type        = string
  default     = "Feature Batch Pipeline"
}

variable "region" {
  default = "europe-west6"
}

variable "zone" {
  default = "europe-west6-c"
}

variable "location" {
  default = "europe-west6"
}