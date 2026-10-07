variable "aws_region" {
  description = "Region the cluster is created in."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Prefix for every resource name."
  type        = string
  default     = "clinicflow"
}

variable "environment" {
  description = "Environment label (dev, staging, prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "availability_zones" {
  description = "Two AZs to spread the subnets across. Leave empty to pick the first two available in the region."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.availability_zones) == 0 || length(var.availability_zones) == 2
    error_message = "availability_zones must be empty (auto) or list exactly two zones."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Must be large enough for four /24 subnets."
  type        = string
  default     = "10.20.0.0/16"
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "Worker node instance type. t3.medium is the smallest that comfortably runs the stack."
  type        = string
  default     = "t3.medium"
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT. SPOT is far cheaper for a demo cluster."
  type        = string
  default     = "SPOT"
}

variable "node_desired_size" {
  description = "Nodes to run at steady state."
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum nodes in the group."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum nodes the group may scale to."
  type        = number
  default     = 4
}

variable "tags" {
  description = "Extra tags applied to every resource."
  type        = map(string)
  default     = {}
}
