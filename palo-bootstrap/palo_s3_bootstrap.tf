#palo_bucket.tf
provider "aws" {
  region = "${var.region}"
  profile = "moo-sbx"
}

##################################
# Palo bootstrap bucket

# Create a bucket for bootstrap files
resource "aws_s3_bucket" "bootstrap_bucket" {
  bucket = "${local.palo_bootstrap_bucket}"
  acl    = "private"

  tags = "${merge( local.default_tags, map (
   "Ci", ""
 ))}"
}

# Create empty folders
locals {
  bootstrap_folders = [
    "config",
    "software",
    "license",
    "content",
  ]
}

# Create the empty folders
resource "aws_s3_bucket_object" "bootstrap_folders" {
  count  = "${length(local.bootstrap_folders)}"
  bucket = "${aws_s3_bucket.bootstrap_bucket.id}"
  acl    = "private"
  key    = "${local.bootstrap_folders[count.index]}/"
  source = "/dev/null"
}

# Define the template variables for the config files
data "template_file" "bootstrap_template" {
  template = "${file(
    join("/", list("bootstrap", local.bootstrap_template)))}"
  vars {
    trusted_subnet_router_ip = "${var.trusted_subnet_router_ip}"
  }
}

# Create the templatized config/bootstrap.xml file
resource "aws_s3_bucket_object" "bootstrap_file" {
  bucket = "${aws_s3_bucket.bootstrap_bucket.id}"
  acl    = "private"
  key    = "${local.bootstrap_template}"
  etag   = "${md5(data.template_file.bootstrap_template.rendered)}"
  content= "${data.template_file.bootstrap_template.rendered}"
}

# Create the config/init-cfg.txt file
resource "aws_s3_bucket_object" "init_file" {
  bucket = "${aws_s3_bucket.bootstrap_bucket.id}"
  acl    = "private"
  key    = "${local.init_file}"
  etag   = "${md5(file(join("/", list("bootstrap", local.init_file))))}"
  source = "bootstrap/${local.init_file}"
}
