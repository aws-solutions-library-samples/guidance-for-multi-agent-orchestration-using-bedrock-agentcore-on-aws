#!/bin/bash
set -e

# Customer Support Assistant Cleanup Script
#
# Removes AWS resources and local files created by this guidance.
# Provides multiple cleanup options to preserve Knowledge Base data if desired.
#
# USAGE:
#   ./cleanup.sh [PROFILE]
#
# ARGUMENTS:
#   PROFILE  AWS CLI profile name (optional, uses AWS_PROFILE env var or default)
#
# OPTIONS:
#   1-4: Clean local files only (preserves AWS resources)
#   5:   Destroy all stacks except Knowledge Base + clean local files
#   6:   Destroy all stacks including Knowledge Base + clean local files
#
# NOTE: Options 5-6 handle region-specific cleanup including frontend stacks in us-east-1

# Use environment variables or defaults
PROFILE="${AWS_PROFILE:-default}"

# Get region from environment, or from profile, or default to us-east-1
if [ -z "$AWS_REGION" ]; then
    if [ "$PROFILE" != "default" ]; then
        REGION=$(aws configure get region --profile $PROFILE 2>/dev/null || echo "us-east-1")
    else
        REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
    fi
else
    REGION="$AWS_REGION"
fi

echo "=== Customer Support Assistant Cleanup ==="
echo "Profile: $PROFILE"
echo "Region: $REGION"
echo ""

# Function to delete test user config file
cleanup_test_users() {
    echo "Deleting test user config file..."
    rm -f ../scripts/test_users_config-${REGION}.json
    rm -f ../tests/integration/test_config.json
    echo "✓ Test user config files removed"
    echo ""
    echo "ℹ️  Note: Cognito users still exist in AWS."
    echo "   To update passwords and regenerate config:"
    echo "   - Run deployment script (generates new random password)"
    echo "   - Or manually: cd scripts && python setup_test_users.py --password '<NewPassword>'"
}

# Function to delete frontend config
cleanup_frontend_config() {
    echo "Cleaning up frontend configuration..."
    rm -f ../frontend/.env.production
    echo "✓ Frontend config removed"
}

# Function to delete deployment outputs
cleanup_deployment_outputs() {
    echo "Cleaning up deployment outputs..."
    rm -f deployment-outputs.json
    rm -rf cdk.out
    echo "✓ Deployment outputs removed"
}

# Function to destroy CDK stacks
destroy_stacks() {
    local skip_kb=$1
    
    echo ""
    echo "Destroying CDK stacks..."
    if [ "$skip_kb" = "true" ]; then
        echo "Knowledge Base will be preserved."
    fi
    echo "This will delete deployed resources."
    read -p "Continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Stack destruction cancelled"
        return
    fi
    
    # Destroy frontend stack first (always in us-east-1)
    echo "Destroying FrontendStack-${REGION} in us-east-1..."
    cdk destroy FrontendStack-${REGION} --profile $PROFILE --region us-east-1 --force || echo "FrontendStack-${REGION} not found or already deleted"
    
    if [ "$skip_kb" = "true" ]; then
        echo "Destroying backend stacks in ${REGION} (preserving KnowledgeBaseStack)..."
        cdk destroy TroubleshootingAgentStack ProductRecommendationAgentStack OrderManagementAgentStack PersonalizationAgentStack CustomerSupportAssistantStack --profile $PROFILE --region $REGION --force
    else
        echo "Destroying all backend stacks in ${REGION}..."
        cdk destroy --all --profile $PROFILE --region $REGION --force
    fi
    
    echo "✓ Stacks destroyed"
    echo ""
    echo "Note: Docker images and layers are not automatically cleaned up."
    echo "To reclaim disk space, you can manually run:"
    echo "  docker system prune -a  # Removes all unused images (affects all projects)"
}

# Main menu
echo "What would you like to clean up?"
echo ""
echo "Local Files Only:"
echo "  1) Test user config (new password generated and pushed to users on next deploy)"
echo "  2) Frontend .env.production (regenerated with current endpoints on next deploy)"
echo "  3) CDK build artifacts (cdk.out/, deployment-outputs.json)"
echo "  4) All local files (options 1-3)"
echo ""
echo "AWS Stacks + Local Files:"
echo "  5) Destroy all stacks except Knowledge Base"
echo "  6) Destroy all stacks including Knowledge Base"
echo ""
echo "  7) Cancel"
echo ""
read -p "Select option (1-7): " option

case $option in
    1)
        cleanup_test_users
        ;;
    2)
        cleanup_frontend_config
        ;;
    3)
        cleanup_deployment_outputs
        ;;
    4)
        cleanup_test_users
        cleanup_frontend_config
        cleanup_deployment_outputs
        echo "✓ All generated files cleaned"
        ;;
    5)
        cleanup_test_users
        cleanup_frontend_config
        cleanup_deployment_outputs
        destroy_stacks true
        echo "✓ Cleanup complete (Knowledge Base preserved)"
        ;;
    6)
        cleanup_test_users
        cleanup_frontend_config
        cleanup_deployment_outputs
        destroy_stacks false
        echo "✓ Complete cleanup finished"
        ;;
    7)
        echo "Cleanup cancelled"
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "=== Cleanup Complete ==="
