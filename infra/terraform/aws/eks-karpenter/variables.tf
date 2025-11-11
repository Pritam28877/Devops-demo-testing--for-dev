variable "name" { type = string }
variable "region" { type = string }
variable "cluster_version" { type = string, default = "1.29" }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "node_instance_type" { type = string, default = "t3.large" }
variable "karpenter_chart_version" { type = string, default = "v0.37.0" }

