variable "name" { type = string }
variable "region" { type = string }
variable "vpc_cidr" { type = string }
variable "private_subnets" { type = list(string) }
variable "public_subnets" { type = list(string) }
variable "instance_type" { type = string, default = "t3.small" }
variable "instance_count" { type = number, default = 3 }
variable "key_name" { type = string }
variable "ami_id" { type = string }
variable "public_instances" { type = bool, default = true }
variable "ssh_cidr_allow" { type = list(string) }
variable "redis_ingress_cidr" { type = list(string), default = ["0.0.0.0/0"] }
variable "redis_port_base" { type = number, default = 7000 }
variable "redis_port_count" { type = number, default = 16 }

