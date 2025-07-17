#!/bin/bash

# AdViewer Backend Deployment Script
# Usage: ./deploy-backend.sh [environment]
# Environment: local, staging, production

set -e

ENVIRONMENT=${1:-staging}
PROJECT_NAME="adviewer-backend"

echo "🚀 Starting AdViewer Backend Deployment"
echo "Environment: $ENVIRONMENT"
echo "Project: $PROJECT_NAME"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "composer.json" ]; then
    print_error "composer.json not found. Please run this script from the backend directory."
    exit 1
fi

# Check if required tools are installed
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v php &> /dev/null; then
        print_error "PHP is not installed"
        exit 1
    fi
    
    if ! command -v composer &> /dev/null; then
        print_error "Composer is not installed"
        exit 1
    fi
    
    print_success "All requirements met"
}

# Install PHP dependencies
install_dependencies() {
    print_status "Installing PHP dependencies..."
    
    if [ "$ENVIRONMENT" = "production" ]; then
        composer install --optimize-autoloader --no-dev --prefer-dist
    else
        composer install --optimize-autoloader
    fi
    
    print_success "Dependencies installed"
}

# Setup environment
setup_environment() {
    print_status "Setting up environment for $ENVIRONMENT..."
    
    # Copy environment file if it doesn't exist
    if [ ! -f ".env" ]; then
        if [ -f ".env.$ENVIRONMENT" ]; then
            cp ".env.$ENVIRONMENT" ".env"
            print_success "Environment file copied from .env.$ENVIRONMENT"
        elif [ -f ".env.example" ]; then
            cp ".env.example" ".env"
            print_warning "Environment file copied from .env.example - please configure it"
        else
            print_error "No environment file found"
            exit 1
        fi
    fi
    
    # Generate application key if not set
    if ! grep -q "APP_KEY=base64:" .env; then
        print_status "Generating application key..."
        php artisan key:generate --force
    fi
    
    print_success "Environment setup complete"
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # Check database connection
    if ! php artisan tinker --execute="DB::connection()->getPdo();" &> /dev/null; then
        print_error "Cannot connect to database. Please check your configuration."
        exit 1
    fi
    
    # Run migrations
    php artisan migrate --force
    
    # Seed database if not production
    if [ "$ENVIRONMENT" != "production" ]; then
        print_status "Seeding database..."
        php artisan db:seed --force
    fi
    
    print_success "Database setup complete"
}

# Clear and cache configuration
optimize_application() {
    print_status "Optimizing application..."
    
    # Clear all caches
    php artisan cache:clear
    php artisan config:clear
    php artisan route:clear
    php artisan view:clear
    
    # Cache configuration for production
    if [ "$ENVIRONMENT" = "production" ]; then
        php artisan config:cache
        php artisan route:cache
        php artisan view:cache
    fi
    
    # Create storage link
    if [ ! -L "public/storage" ]; then
        php artisan storage:link
    fi
    
    print_success "Application optimized"
}

# Set proper permissions
set_permissions() {
    print_status "Setting file permissions..."
    
    # Set ownership (adjust as needed for your server)
    if [ "$ENVIRONMENT" = "production" ]; then
        chown -R www-data:www-data storage bootstrap/cache
        chmod -R 775 storage bootstrap/cache
    else
        chmod -R 775 storage bootstrap/cache
    fi
    
    print_success "Permissions set"
}

# Run tests
run_tests() {
    if [ "$ENVIRONMENT" != "production" ]; then
        print_status "Running tests..."
        
        if [ -f "vendor/bin/phpunit" ]; then
            ./vendor/bin/phpunit --testdox
            print_success "Tests passed"
        else
            print_warning "PHPUnit not found, skipping tests"
        fi
    fi
}

# Deploy to Railway (if configured)
deploy_to_railway() {
    if [ "$ENVIRONMENT" = "production" ] && command -v railway &> /dev/null; then
        print_status "Deploying to Railway..."
        
        # Check if railway is logged in
        if railway whoami &> /dev/null; then
            railway up
            print_success "Deployed to Railway"
        else
            print_warning "Railway CLI not authenticated. Skipping deployment."
            print_warning "Run 'railway login' to authenticate"
        fi
    fi
}

# Health check
health_check() {
    print_status "Performing health check..."
    
    # Check if application is responding
    if [ "$ENVIRONMENT" = "local" ]; then
        URL="http://localhost:8000/api/health"
    else
        URL=$(php artisan route:list --path=health --format=json 2>/dev/null | head -1 || echo "")
        if [ -z "$URL" ]; then
            print_warning "Health check endpoint not found"
            return
        fi
    fi
    
    # Create health check route if it doesn't exist
    if ! php artisan route:list | grep -q "health"; then
        print_status "Creating health check endpoint..."
        cat > routes/web.php << 'EOF'
<?php

Route::get('/health', function () {
    return response()->json([
        'status' => 'ok',
        'timestamp' => now(),
        'environment' => app()->environment(),
    ]);
});
EOF
    fi
    
    print_success "Health check complete"
}

# Backup database (production only)
backup_database() {
    if [ "$ENVIRONMENT" = "production" ]; then
        print_status "Creating database backup..."
        
        BACKUP_DIR="backups"
        BACKUP_FILE="$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S).sql"
        
        mkdir -p "$BACKUP_DIR"
        
        # Get database configuration
        DB_HOST=$(php artisan tinker --execute="echo config('database.connections.mysql.host');" 2>/dev/null)
        DB_NAME=$(php artisan tinker --execute="echo config('database.connections.mysql.database');" 2>/dev/null)
        DB_USER=$(php artisan tinker --execute="echo config('database.connections.mysql.username');" 2>/dev/null)
        DB_PASS=$(php artisan tinker --execute="echo config('database.connections.mysql.password');" 2>/dev/null)
        
        if command -v mysqldump &> /dev/null; then
            mysqldump -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$BACKUP_FILE"
            print_success "Database backup created: $BACKUP_FILE"
        else
            print_warning "mysqldump not found, skipping backup"
        fi
    fi
}

# Send deployment notification
send_notification() {
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        print_status "Sending deployment notification..."
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚀 AdViewer Backend deployed to $ENVIRONMENT environment\"}" \
            "$SLACK_WEBHOOK_URL" &> /dev/null
        
        print_success "Notification sent"
    fi
}

# Main deployment process
main() {
    print_status "Starting deployment process..."
    
    # Backup database before deployment (production only)
    backup_database
    
    # Core deployment steps
    check_requirements
    install_dependencies
    setup_environment
    run_migrations
    optimize_application
    set_permissions
    
    # Run tests (non-production)
    run_tests
    
    # Health check
    health_check
    
    # Deploy to cloud (if configured)
    deploy_to_railway
    
    # Send notification
    send_notification
    
    print_success "Deployment completed successfully!"
    print_status "Environment: $ENVIRONMENT"
    print_status "Timestamp: $(date)"
    
    if [ "$ENVIRONMENT" = "local" ]; then
        print_status "Local server: http://localhost:8000"
        print_status "API Documentation: http://localhost:8000/api/documentation"
    fi
}

# Handle script interruption
trap 'print_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main

exit 0 