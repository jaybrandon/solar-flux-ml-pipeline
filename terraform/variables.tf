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
  description = "GitHub personal access token with access to the repository and variable/secret write permission"
  type        = string
}

variable "wandb_entity" {
  description = "Wandb entity for tracking"
  type        = string
}

variable "wandb_project" {
  description = "Wandb project for tracking"
  type        = string
}

variable "wandb_api_key" {
  description = "Wandb api key"
  type        = string
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