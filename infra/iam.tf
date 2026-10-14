data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "doc_service" {
  name               = "doc-service-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy" "doc_service" {
  name = "doc-service-access"
  role = aws_iam_role.doc_service.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "MemberDocsObjectReadWrite"
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject"]
      Resource = "${aws_s3_bucket.member_docs.arn}/*"
    }]
  })
}

resource "aws_iam_instance_profile" "doc_service" {
  name = "doc-service-${var.env}"
  role = aws_iam_role.doc_service.name
}

resource "aws_iam_role" "claims_api" {
  name               = "claims-api-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy" "claims_api" {
  name = "claims-api-access"
  role = aws_iam_role.claims_api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:aws:secretsmanager:${var.region}:111122223333:secret:claims-api/*"
    }]
  })
}
