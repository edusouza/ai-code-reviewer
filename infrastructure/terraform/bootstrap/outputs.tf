output "state_bucket_name" {
  description = "Name of the GCS bucket for Terraform state"
  value       = google_storage_bucket.terraform_state.name
}

output "kms_key_id" {
  description = "KMS key ID for state encryption"
  value       = google_kms_crypto_key.terraform_state.id
}

output "key_ring_id" {
  description = "KMS key ring ID"
  value       = google_kms_key_ring.terraform.id
}
