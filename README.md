# ECS update monitor terraform module

[![Build Status](https://travis-ci.org/mergermarket/tf_ecs_update_monitor.svg?branch=master)](https://travis-ci.org/mergermarket/tf_ecs_update_monitor)

This module can be used to wait for an update to an ECS service to apply.

## Dependencies

This module depends on a python interpretter (2 or 3) and the boto3 module
installed.

## Input variables

* `cluster` - (required) The ECS cluster that the service is deployed to.
* `service` - (required) The name of the ECS service.
* `taskdef` - (required) The task definition ARN that the service is being updated to.

## Example usage

If you are building a service, the chances are that you will be using a higher
level module that includes this module. However, the following demonstrates how
you might use this (e.g. in such a module):

    resource "aws_ecs_task_definition" "taskdef" {
      family                = "my-service"
      container_definitions = "..."
    }
    
    resource "aws_ecs_service" "service" {
      name            = "my-service"
      task_definition = "${aws_ecs_task_definition.taskdef.arn}"
      cluster         = "my-cluster"
      desired_count   = "2"
    }
    
    module "ecs_update_monitor" {
      source = "github.com/mergermarket/tf_ecs_update_monitor"

      cluster = "my-cluster"
      service = "my-service"
      taskdef = "${aws_ecs_task_definition.taskdef.arn}"
    }

## Output

The module outputs information about the progress of the update to the user,
exiting with a non-zero exit status should the deployment fail.
