resource "aws_instance" "doc_service" {
  ami                  = "ami-0abcdef1234567890"
  instance_type        = "t3.medium"
  iam_instance_profile = aws_iam_instance_profile.doc_service.name
  tags = {
    Name    = "doc-svc-prod-01"
    Service = "doc-service"
  }
}

resource "aws_instance" "claims_api" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.medium"
  tags = {
    Name    = "claims-api-prod-01"
    Service = "claims-api"
  }
}
