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

resource "aws_s3_bucket_object" "bootstrap_folders" {
  count  = "${length(local.bootstrap_folders)}"
  bucket = "${aws_s3_bucket.bootstrap_bucket.id}"
  acl    = "private"
  key    = "${local.bootstrap_folders[count.index]}/"
  source = "/dev/null"
}

# Copy config files
locals {
  bootstrap_files = [
    "config/bootstrap.xml",
    "config/init-cfg.txt",
  ]
}

resource "aws_s3_bucket_object" "bootstrap_files" {
  count  = "${length(local.bootstrap_files)}"
  bucket = "${aws_s3_bucket.bootstrap_bucket.id}"
  acl    = "private"
  key    = "${local.bootstrap_files[count.index]}"
  source = "./bootstrap/${local.bootstrap_files[count.index]}"
  etag   = "${md5(file("./bootstrap/${local.bootstrap_files[count.index]}"))}"
}
