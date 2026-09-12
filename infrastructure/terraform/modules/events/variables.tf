variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
}

variable "event_bus_name" {
  type        = string
  description = "Name of the custom EventBridge bus"
  default     = "jarvis-event-bus"
}
