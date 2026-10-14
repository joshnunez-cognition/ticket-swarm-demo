mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

run "doc_service_policy_is_least_privilege" {
  command = apply

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.doc_service.policy).Statement :
      !contains(flatten([s.Action]), "*") && !contains(flatten([s.Resource]), "*")
    ])
    error_message = "doc-service-access must not grant wildcard Action or Resource."
  }

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.doc_service.policy).Statement :
      alltrue([for a in flatten([s.Action]) : contains(["s3:PutObject", "s3:GetObject"], a)])
    ])
    error_message = "doc-service-access may only allow s3:PutObject and s3:GetObject."
  }

  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.doc_service.policy).Statement :
      alltrue([for r in flatten([s.Resource]) : r == "${aws_s3_bucket.member_docs.arn}/*"])
    ])
    error_message = "doc-service-access must be scoped to objects in the member docs bucket."
  }
}
