output "offline_feature_store_url" {
  value = google_storage_bucket.offline_feature_store.url
}

output "online_feature_store_url" {
  value = google_storage_bucket.online_feature_store.url
}