terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.53"
    }
  }
}

provider "aws" {
  region = var.region
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${var.name}-vpc"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway = true
  single_nat_gateway = true
}

data "aws_availability_zones" "available" {}

resource "aws_security_group" "redis" {
  name        = "${var.name}-redis-sg"
  description = "Allow Redis cluster and SSH"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_cidr_allow
  }

  # Redis instance port base..base+N (example 7000-7015)
  dynamic "ingress" {
    for_each = toset(range(var.redis_port_base, var.redis_port_base + var.redis_port_count - 1))
    content {
      description = "Redis ${ingress.value}"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = var.redis_ingress_cidr
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_launch_template" "redis" {
  name_prefix   = "${var.name}-lt-"
  image_id      = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name

  network_interfaces {
    security_groups             = [aws_security_group.redis.id]
    associate_public_ip_address = var.public_instances
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.name}-redis"
    }
  }
}

resource "aws_autoscaling_group" "redis" {
  name                      = "${var.name}-asg"
  max_size                  = var.instance_count
  min_size                  = var.instance_count
  desired_capacity          = var.instance_count
  vpc_zone_identifier       = var.public_instances ? module.vpc.public_subnets : module.vpc.private_subnets
  health_check_type         = "EC2"
  health_check_grace_period = 120

  launch_template {
    id      = aws_launch_template.redis.id
    version = "$Latest"
  }
}

output "redis_private_ips" {
  value = aws_autoscaling_group.redis.instances[*].ipv4_addresses
}

output "security_group_id" {
  value = aws_security_group.redis.id
}

