# 0. Pre-create Log Groups (Fixes AccessDenied Error)
resource "aws_cloudwatch_log_group" "eta_engine_logs" {
  name              = "/ecs/eta-engine"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "osrm_backend_logs" {
  name              = "/ecs/osrm-backend"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "redis_logs" {
  name              = "/ecs/redis"
  retention_in_days = 7
  
}
# 1. The Cluster (The parking lot for your containers)
resource "aws_ecs_cluster" "main" {
  name = "eta-engine-cluster"
}

# 2. IAM Role (Permission to pull images from ECR)
resource "aws_iam_role" "ecs_execution_role" {
  name = "eta_ecs_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# Attach standard permissions (CloudWatch Logs, ECR Pull)
resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# 3. Security Group (Firewall)
resource "aws_security_group" "ecs_sg" {
  name        = "eta-ecs-sg"
  description = "Allow traffic from ALB"
  vpc_id      = aws_vpc.main.id

  # Inbound: Allow HTTP (8000) only from the Load Balancer (we will add ALB later)
  # For now, we allow from everywhere for testing, or strictly internal.
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # We will tighten this later
  }

  # Outbound: Allow everything (Downloading updates, talking to Redis)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 4. Task Definition (The Blueprint)
resource "aws_ecs_task_definition" "app" {
  family                   = "eta-engine-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 2048 # 1 vCPU
  memory                   = 8192 # 3 GB RAM (Needed for OSRM Map)
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "eta-engine"
      image     = aws_ecr_repository.eta_engine.repository_url
      essential = true
      portMappings = [{ containerPort = 8000 }]
      environment = [
        { name = "OSRM_HOST", value = "http://localhost:5000" },
        { name = "REDIS_HOST", value = "localhost" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/eta-engine"
          "awslogs-region"        = "ap-south-2"
          "awslogs-stream-prefix" = "ecs"
        }
      }
    },
    {
      name      = "osrm-backend"
      image     = aws_ecr_repository.osrm_backend.repository_url
      essential = true
      portMappings = [{ containerPort = 5000 }]
      memoryReservation = 2048
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/osrm-backend"
          "awslogs-region"        = "ap-south-2"
          "awslogs-stream-prefix" = "ecs"
        }
      }
    },
    {
      name      = "redis"
      image     = "redis:6-alpine"
      essential = true
      portMappings = [{ containerPort = 6379 }]
      memoryReservation = 256
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/redis"
          "awslogs-region"        = "ap-south-2"
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }

  ])
}

# 5. The Service (Keep it running)
resource "aws_ecs_service" "app" {
  name            = "eta-engine-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id] # Public for now to simplify download
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = true # Needed to pull images from ECR without a NAT Gateway
  }
}