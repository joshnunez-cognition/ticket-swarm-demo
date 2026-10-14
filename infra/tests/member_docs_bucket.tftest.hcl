mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
  mock_resource "aws_s3_bucket" {
    defaults = {
      arn = "arn:aws:s3:::demo-health-member-docs"
    }
  }
}

run "member_docs_bucket_is_not_public" {
  command = apply

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.member_docs.block_public_acls,
      aws_s3_bucket_public_access_block.member_docs.block_public_policy,
      aws_s3_bucket_public_access_block.member_docs.ignore_public_acls,
      aws_s3_bucket_public_access_block.member_docs.restrict_public_buckets,
    ])
    error_message = "demo-health-member-docs (PHI) must enable all four Block Public Access settings."
  }

  assert {
    condition = length([
      for s in jsondecode(aws_s3_bucket_policy.member_docs.policy).Statement : s
      if s.Effect == "Allow" && (try(s.Principal == "*", false) || try(s.Principal.AWS == "*", false))
    ]) == 0
    error_message = "demo-health-member-docs (PHI) bucket policy must not Allow Principal \"*\"."
  }
}
