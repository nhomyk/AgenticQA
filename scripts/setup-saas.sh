#!/bin/bash
set -e

echo "🚀 Setting up OrbitQA SaaS Platform..."
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
  echo "❌ Docker not found. Please install Docker first."
  exit 1
fi

echo "✅ Docker found"

# Copy .env if not exists
if [ ! -f .env ]; then
  echo "📝 Creating .env file from template..."
  cp .env.example .env
  echo "⚠️  Please update .env with your configuration"
fi

# Build images
echo "🏗️  Building Docker images..."
docker-compose build

# Create databases
echo "📊 Setting up databases..."
docker-compose up -d postgres redis

# Wait for postgres
echo "⏳ Waiting for PostgreSQL..."
sleep 5

# Initialize database schema
echo "🗄️  Initializing database schema..."
docker-compose exec -T postgres psql -U postgres -d orbitqa_saas -f - < saas-db-schema.sql 2>/dev/null || echo "Note: Schema may already exist"

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d

echo ""
echo "✅ OrbitQA SaaS Platform is running!"
echo ""
echo "📊 Access Points:"
echo "  🤖 QA Agent:       http://localhost:3000"
echo "  📱 SaaS Dashboard: http://localhost:3001"
echo "  📈 Prometheus:     http://localhost:9090"
echo "  🔍 Jaeger Traces:  http://localhost:16686"
echo "  💾 PostgreSQL:     localhost:5432"
echo "  📦 Redis:          localhost:6379"
echo ""
echo "🔑 Default Credentials:"
echo "  Database User: postgres"
echo "  Database Name: orbitqa_saas"
echo ""
echo "📚 Next Steps:"
echo "  1. Create an account in the SaaS dashboard"
echo "  2. Start a test run from the dashboard"
echo "  3. View results in real-time"
echo ""
echo "🛑 To stop all services:"
echo "  docker-compose down"
echo ""
echo "📖 View logs:"
echo "  docker-compose logs -f"
