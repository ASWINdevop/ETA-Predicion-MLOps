# 1. API Repository
resource "aws_ecr_repository" "eta_engine" {
  name                 = "eta-engine"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # Allows deleting repo even if it has images

  image_scanning_configuration {
    scan_on_push = true
  }
}

# 2. OSRM Repository
resource "aws_ecr_repository" "osrm_backend" {
  name                 = "osrm-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# 3. Output the URLs (We need these to push images later)
output "ecr_repo_url_api" {
  value = aws_ecr_repository.eta_engine.repository_url
}

output "ecr_repo_url_osrm" {
  value = aws_ecr_repository.osrm_backend.repository_url
}