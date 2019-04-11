variable "region" {
  default = "us-west-2"
}

locals {
  palo_bootstrap_bucket = "${var.deptName}-${var.envName}-${var.appName}-bootstrap"
}

variable "deptName" {
  default = "css"
}

variable "appName" {
  default = "palo"
}

variable "envName" {
  default = "sbx"
}

variable "trusted_subnet_router_ip" {
  description = "The router for the trusted subnet (usually .1)"
}

# Copy these config files unaltered
locals {
  bootstrap_template = "config/bootstrap.xml",
  init_file = "config/init-cfg.txt",
}

locals {
  # tags that we'll add to every resource in this workspace
  default_tags = "${map(
    "Department", "${var.deptName}",
    "Application", "${var.appName}",
    "Environment", "${var.envName}"
    )}"
}
