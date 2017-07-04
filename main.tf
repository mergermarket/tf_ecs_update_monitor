variable "cluster" {
  description = "The ECS cluster that the service is deployed to."
  type        = "string"
}

variable "service" {
  description = "The name of the ECS service."
  type        = "string"
}

variable "taskdef" {
  description = "The task definition ARN that the service is being updated to."
  type        = "string"
}

data "aws_region" "current" {
  current = true
}

resource "null_resource" "ecs_update_monitor" {
  triggers {
    cluster = "${var.cluster}"
    service = "${var.service}"
    taskdef = "${var.taskdef}"
    region  = "${data.aws_region.current.name}"
  }

  provisioner "local-exec" {
    command = "${path.module}/provision.sh '${path.module}' '${var.cluster}' '${var.service}' '${var.taskdef}' '${data.aws_region.current.name}'"
  }
}
