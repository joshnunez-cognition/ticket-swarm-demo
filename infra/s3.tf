resource "aws_s3_bucket" "member_docs" {
  bucket = "demo-health-member-docs"
  tags = {
    Service   = "doc-service"
    DataClass = "phi"
  }
}

resource "aws_s3_bucket_public_access_block" "member_docs" {
  bucket                  = aws_s3_bucket.member_docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "member_docs" {
  bucket = aws_s3_bucket.member_docs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.member_docs.arn,
        "${aws_s3_bucket.member_docs.arn}/*",
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

# Marketing site assets. Public by design: logos, CSS, help-center images.
resource "aws_s3_bucket" "static_site_assets" {
  bucket = "demo-health-static-site-assets"
  tags = {
    Service   = "member-portal"
    DataClass = "public"
    Purpose   = "public-website"
  }
}

resource "aws_s3_bucket_public_access_block" "static_site_assets" {
  bucket                  = aws_s3_bucket.static_site_assets.id
  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "static_site_assets" {
  bucket = aws_s3_bucket.static_site_assets.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicWebsiteRead"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.static_site_assets.arn}/*"
    }]
  })
}
