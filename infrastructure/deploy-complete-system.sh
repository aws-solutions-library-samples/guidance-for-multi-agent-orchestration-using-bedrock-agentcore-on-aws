#!/bin/bash
set -e

# Complete System Deployment Script
# This script deploys all stacks in the correct order and verifies outputs

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Usage
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "Usage: ./deploy-complete-system.sh [PROFILE] [REGION]"
    echo ""
    echo "This script deploys the complete Customer Support Assistant system:"
    echo "  1. Build CDK infrastructure"
    echo "  2. Bootstrap CDK (if needed)"
    echo "  3. Build frontend (initial build)"
    echo "  4. Deploy all stacks (CDK handles dependencies and parallelizes)"
    echo "  5. Configure frontend with stack outputs"
    echo "  6. Upload frontend to S3"
    echo "  7. Invalidate CloudFront cache"
    echo "  8. Verify all stack outputs"
    echo "  9. Configure runtime authorization headers"
    echo ""
    echo "Arguments:"
    echo "  PROFILE  AWS profile name (optional, uses AWS CLI default if not specified)"
    echo "  REGION   AWS region (optional, uses profile's default region or us-east-1)"
    echo ""
    echo "Examples:"
    echo "  ./deploy-complete-system.sh                        # Use AWS CLI defaults"
    echo "  ./deploy-complete-system.sh my-profile             # Custom profile"
    echo "  ./deploy-complete-system.sh my-profile us-west-2   # Custom profile and region"
    exit 0
fi

# Arguments
PROFILE="$1"
REGION="$2"

# Build profile flag if provided
PROFILE_FLAG=""
if [ -n "$PROFILE" ]; then
    PROFILE_FLAG="--profile $PROFILE"
    export AWS_PROFILE=$PROFILE
fi

# If region not specified, try to get from profile
if [ -z "$REGION" ]; then
    if [ -n "$PROFILE" ]; then
        REGION=$(aws configure get region $PROFILE_FLAG 2>/dev/null || echo "us-east-1")
    else
        REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
    fi
fi

export AWS_REGION=$REGION
ACCOUNT=$(aws sts get-caller-identity $PROFILE_FLAG --query Account --output text)

echo -e "${BLUE}========================================================================"
echo "Customer Support Assistant - Complete System Deployment"
echo "========================================================================${NC}"
echo -e "Profile: ${YELLOW}${PROFILE:-<AWS CLI default>}${NC}"
echo -e "Region: ${YELLOW}$REGION${NC}"
echo -e "Account: ${YELLOW}$ACCOUNT${NC}"
echo ""

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BLUE}========================================================================"
    echo "$1"
    echo -e "========================================================================${NC}"
}

# Function to check if stack exists
stack_exists() {
    local stack_name=$1
    aws cloudformation describe-stacks \
        $PROFILE_FLAG \
        --region $REGION \
        --stack-name "$stack_name" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null
}

# Function to get stack output
get_stack_output() {
    local stack_name=$1
    local output_key=$2
    local region=${3:-$REGION}  # Use provided region or default to $REGION
    aws cloudformation describe-stacks \
        $PROFILE_FLAG \
        --region $region \
        --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text 2>/dev/null
}

# Build CDK infrastructure
print_section "📦 Step 1: Building CDK Infrastructure"
cd "$(dirname "$0")"

echo "Installing CDK dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ npm install failed${NC}"
    exit 1
fi

npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ CDK build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ CDK build complete${NC}"

# Bootstrap CDK if needed
print_section "🚀 Step 2: Checking CDK Bootstrap"
if ! aws cloudformation describe-stacks $PROFILE_FLAG --region $REGION --stack-name CDKToolkit &>/dev/null; then
    echo "CDK not bootstrapped in this region. Bootstrapping..."
    cdk bootstrap $PROFILE_FLAG --region $REGION
    echo -e "${GREEN}✅ CDK bootstrap complete${NC}"
else
    # Check bootstrap version
    BOOTSTRAP_VERSION=$(aws cloudformation describe-stacks $PROFILE_FLAG --region $REGION --stack-name CDKToolkit --query 'Stacks[0].Outputs[?OutputKey==`BootstrapVersion`].OutputValue' --output text 2>/dev/null || echo "0")
    REQUIRED_VERSION=21
    
    if [ "$BOOTSTRAP_VERSION" -lt "$REQUIRED_VERSION" ]; then
        echo -e "${YELLOW}⚠️  CDK bootstrap stack is outdated${NC}"
        echo "   Current version: $BOOTSTRAP_VERSION"
        echo "   Required version: $REQUIRED_VERSION"
        echo ""
        echo "The bootstrap stack needs to be upgraded. This is safe and backward compatible,"
        echo "but may affect other CDK applications in this account/region."
        echo ""
        read -p "Upgrade bootstrap stack? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Upgrading CDK bootstrap..."
            cdk bootstrap $PROFILE_FLAG --region $REGION
            echo -e "${GREEN}✅ CDK bootstrap upgraded${NC}"
        else
            echo -e "${RED}❌ Deployment cannot proceed with outdated bootstrap${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ CDK bootstrap is up to date (version $BOOTSTRAP_VERSION)${NC}"
    fi
fi

# Build frontend application early (creates dist folder for CDK asset bundling)
print_section "🏗️  Step 3: Building Frontend Application"
cd ../frontend

echo "Installing frontend dependencies..."
npm install

echo "Building frontend (initial build for CDK)..."
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend build complete${NC}"

cd ../infrastructure

# Deploy all stacks
print_section "📦 Step 4: Deploying All Stacks"
echo "Deploying all stacks (CDK will handle dependencies and parallelize where possible):"
echo "  - CustomerSupportAssistantStack (Supervisor + Cognito + Memory)"
echo "  - KnowledgeBaseStack (Knowledge Bases)"
echo "  - PersonalizationAgentStack"
echo "  - OrderManagementAgentStack"
echo "  - ProductRecommendationAgentStack"
echo "  - TroubleshootingAgentStack"
echo "  - FrontendStack-${REGION} (S3 + CloudFront + WAF in us-east-1)"
echo ""

cdk deploy --all \
    $PROFILE_FLAG \
    --require-approval never

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Stack deployment failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ All stacks deployed${NC}"

# Setup frontend configuration from stack outputs
print_section "⚙️  Step 5: Configuring Frontend with Stack Outputs"
cd ../frontend

echo "Setting up frontend configuration from deployed stacks..."
npm run setup-config -- --region $REGION

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend configuration setup failed${NC}"
    exit 1
fi

# Rebuild frontend with configuration
echo "Rebuilding frontend with configuration..."
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend rebuild failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend configured and rebuilt${NC}"

cd ../infrastructure

# Upload frontend build to S3
print_section "📤 Step 6: Uploading Frontend to S3"

# Get S3 bucket name from stack output (stack name includes region, always in us-east-1)
FRONTEND_BUCKET=$(get_stack_output "FrontendStack-${REGION}" "BucketName" "us-east-1")

if [ -z "$FRONTEND_BUCKET" ]; then
    echo -e "${RED}❌ Could not get S3 bucket name from FrontendStack-${REGION}${NC}"
    exit 1
fi

echo "Uploading frontend build to S3 bucket: $FRONTEND_BUCKET"
cd ../frontend

aws s3 sync dist/ s3://$FRONTEND_BUCKET/ \
    $PROFILE_FLAG \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "index.html" \
    --exclude "*.map"

# Upload index.html separately with no-cache
aws s3 cp dist/index.html s3://$FRONTEND_BUCKET/index.html \
    $PROFILE_FLAG \
    --cache-control "no-cache, no-store, must-revalidate"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend upload failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend uploaded to S3${NC}"

# Invalidate CloudFront cache
print_section "🔄 Step 7: Invalidating CloudFront Cache"

DISTRIBUTION_ID=$(get_stack_output "FrontendStack-${REGION}" "DistributionId" "us-east-1")

if [ -z "$DISTRIBUTION_ID" ]; then
    echo -e "${RED}❌ Could not get CloudFront distribution ID${NC}"
    exit 1
fi

echo "Creating CloudFront invalidation for distribution: $DISTRIBUTION_ID"
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    $PROFILE_FLAG \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ CloudFront invalidation failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ CloudFront invalidation created: $INVALIDATION_ID${NC}"
echo "Note: Invalidation may take 5-10 minutes to complete"

cd ../infrastructure

# Verify all stack outputs
print_section "🔍 Step 8: Verifying Stack Outputs"

echo ""
echo "Checking CustomerSupportAssistantStack outputs..."
SUPERVISOR_ARN=$(get_stack_output "CustomerSupportAssistantStack" "SupervisorAgentRuntimeArn")
USER_POOL_ID=$(get_stack_output "CustomerSupportAssistantStack" "UserPoolId")
USER_POOL_CLIENT_ID=$(get_stack_output "CustomerSupportAssistantStack" "UserPoolClientId")
MEMORY_ID=$(get_stack_output "CustomerSupportAssistantStack" "MemoryId")

if [ -z "$SUPERVISOR_ARN" ] || [ -z "$USER_POOL_ID" ] || [ -z "$USER_POOL_CLIENT_ID" ]; then
    echo -e "${RED}❌ Missing required outputs from CustomerSupportAssistantStack${NC}"
    exit 1
fi
echo -e "${GREEN}✅ CustomerSupportAssistantStack outputs verified${NC}"

echo ""
echo "Checking KnowledgeBaseStack outputs..."
PERSONALIZATION_KB=$(get_stack_output "KnowledgeBaseStack" "PersonalizationKnowledgeBaseId")
TROUBLESHOOTING_KB=$(get_stack_output "KnowledgeBaseStack" "TroubleshootingKnowledgeBaseId")

if [ -z "$PERSONALIZATION_KB" ] || [ -z "$TROUBLESHOOTING_KB" ]; then
    echo -e "${RED}❌ Missing required outputs from KnowledgeBaseStack${NC}"
    exit 1
fi
echo -e "${GREEN}✅ KnowledgeBaseStack outputs verified${NC}"

echo ""
echo "Checking agent stack outputs..."
PERSONALIZATION_ARN=$(get_stack_output "PersonalizationAgentStack" "PersonalizationAgentRuntimeArn")
ORDER_MGMT_ARN=$(get_stack_output "OrderManagementAgentStack" "OrderManagementAgentRuntimeArn")
PRODUCT_REC_ARN=$(get_stack_output "ProductRecommendationAgentStack" "ProductRecommendationAgentRuntimeArn")
TROUBLESHOOTING_ARN=$(get_stack_output "TroubleshootingAgentStack" "TroubleshootingAgentRuntimeArn")

if [ -z "$PERSONALIZATION_ARN" ] || [ -z "$ORDER_MGMT_ARN" ] || [ -z "$PRODUCT_REC_ARN" ] || [ -z "$TROUBLESHOOTING_ARN" ]; then
    echo -e "${RED}❌ Missing required outputs from agent stacks${NC}"
    exit 1
fi
echo -e "${GREEN}✅ All agent stack outputs verified${NC}"

echo ""
echo "Checking FrontendStack-${REGION} outputs..."
WEBSITE_URL=$(get_stack_output "FrontendStack-${REGION}" "WebsiteURL" "us-east-1")
DISTRIBUTION_ID=$(get_stack_output "FrontendStack-${REGION}" "DistributionId" "us-east-1")

if [ -z "$WEBSITE_URL" ] || [ -z "$DISTRIBUTION_ID" ]; then
    echo -e "${RED}❌ Missing required outputs from FrontendStack-${REGION}${NC}"
    exit 1
fi
echo -e "${GREEN}✅ FrontendStack-${REGION} outputs verified${NC}"

# Display deployment summary
print_section "📋 Deployment Summary"

echo ""
echo -e "${GREEN}✅ All stacks deployed successfully!${NC}"
echo ""
echo "Stack Outputs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "CustomerSupportAssistantStack:"
echo "  Supervisor Runtime ARN: $SUPERVISOR_ARN"
echo "  User Pool ID: $USER_POOL_ID"
echo "  User Pool Client ID: $USER_POOL_CLIENT_ID"
echo "  Memory ID: $MEMORY_ID"
echo ""
echo "KnowledgeBaseStack:"
echo "  Personalization KB ID: $PERSONALIZATION_KB"
echo "  Troubleshooting KB ID: $TROUBLESHOOTING_KB"
echo ""
echo "Agent Stacks:"
echo "  Personalization Agent: $PERSONALIZATION_ARN"
echo "  Order Management Agent: $ORDER_MGMT_ARN"
echo "  Product Recommendation Agent: $PRODUCT_REC_ARN"
echo "  Troubleshooting Agent: $TROUBLESHOOTING_ARN"
echo ""
echo "FrontendStack-${REGION} (always deployed in us-east-1):"
echo "  Website URL: $WEBSITE_URL"
echo "  CloudFront Distribution ID: $DISTRIBUTION_ID"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Save outputs to file
OUTPUT_FILE="deployment-outputs.json"
cat > "$OUTPUT_FILE" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "region": "$REGION",
  "account": "$ACCOUNT",
  "stacks": {
    "CustomerSupportAssistantStack": {
      "supervisorRuntimeArn": "$SUPERVISOR_ARN",
      "userPoolId": "$USER_POOL_ID",
      "userPoolClientId": "$USER_POOL_CLIENT_ID",
      "memoryId": "$MEMORY_ID"
    },
    "KnowledgeBaseStack": {
      "personalizationKnowledgeBaseId": "$PERSONALIZATION_KB",
      "troubleshootingKnowledgeBaseId": "$TROUBLESHOOTING_KB"
    },
    "AgentStacks": {
      "personalizationAgentRuntimeArn": "$PERSONALIZATION_ARN",
      "orderManagementAgentRuntimeArn": "$ORDER_MGMT_ARN",
      "productRecommendationAgentRuntimeArn": "$PRODUCT_REC_ARN",
      "troubleshootingAgentRuntimeArn": "$TROUBLESHOOTING_ARN"
    },
    "FrontendStack-${REGION}": {
      "websiteUrl": "$WEBSITE_URL",
      "distributionId": "$DISTRIBUTION_ID"
    }
  }
}
EOF

echo ""
echo -e "${GREEN}✅ Deployment outputs saved to: $OUTPUT_FILE${NC}"

# Configure runtime authorization headers
print_section "🔐 Step 9: Configuring Runtime Authorization Headers"

echo ""
echo "Configuring Authorization header pass-through for all agent runtimes..."
echo ""

# Configure all runtimes (auto-discovers from CloudFormation)
echo -e "${YELLOW}Configuring runtime authorization headers...${NC}"
cd ../scripts
if python fix_all_runtime_auth.py --region "$REGION" $PROFILE_FLAG; then
    echo -e "${GREEN}✅ All runtimes configured successfully${NC}"
else
    echo -e "${RED}❌ Failed to configure some runtimes${NC}"
    echo ""
    echo "You may need to manually configure runtimes using:"
    echo "  python ../scripts/fix_all_runtime_auth.py --region $REGION $PROFILE_FLAG"
fi
cd ../infrastructure
echo ""

# Create test users automatically with random password
print_section "👥 Creating Test Users"
echo ""
cd ../scripts

# Check if test users already exist
if [ -f "test_users_config-${REGION}.json" ]; then
    echo -e "${YELLOW}Test users config already exists.${NC}"
    echo "Updating config with new CDK outputs..."
    if python setup_test_users.py --config-only; then
        echo -e "${GREEN}✅ Configuration updated${NC}"
        echo ""
        # Read and display users from JSON
        python3 << EOF
import json
import os
region = os.environ.get('AWS_REGION', 'us-east-1')
with open(f'test_users_config-{region}.json', 'r') as f:
    config = json.load(f)
    users = config.get('users', [])
    if users:
        print(f"Test user accounts:")
        for user in users:
            print(f"  - {user['email']} ({user['customer_id']})")
        print(f"")
        password = users[0].get('password', 'N/A')
        print(f"Test users password for all accounts:")
        print(f"  {password}")
EOF
        echo ""
        echo -e "${YELLOW}⚠️  Password available in scripts/test_users_config-${REGION}.json${NC}"
        echo ""
        echo "To reset users with new password:"
        echo "  cd scripts"
        echo "  python setup_test_users.py --password '<YourSecurePassword>'"
    else
        echo -e "${RED}❌ Failed to update configuration${NC}"
    fi
else
    # Generate random password that meets Cognito requirements (12+ chars, mixed case, numbers, symbols)
    TEST_PASSWORD=$(openssl rand -base64 12 | tr -d "=+/" | cut -c1-12)Aa1!
    echo ""
    if python setup_test_users.py --password "${TEST_PASSWORD}"; then
        echo -e "${GREEN}✅ Test users created successfully${NC}"
        echo ""
        echo "Test user accounts:"
        echo "  - mateo_jackson@example.com (cust001)"
        echo "  - martha_rivera@example.com (cust002)"
        echo "  - carlos_salazar@example.com (cust003)"
        echo "  - richard_roe@example.com (cust004)"
        echo "  - jane_doe@example.com (cust005)"
        echo "  - mary_major@example.com (cust006)"
        echo "  - diego_ramirez@example.com (cust007)"
        echo "  - saanvi_sarkar@example.com (cust008)"
        echo "  - jorge_souza@example.com (cust009)"
        echo "  - shirley_rodriguez@example.com (cust010)"
        echo ""
        echo "Generated test user password for all accounts:"
        echo "  ${TEST_PASSWORD}"
        echo ""
        echo -e "${YELLOW}⚠️  Password saved in scripts/test_users_config-${REGION}.json${NC}"
    else
        echo -e "${YELLOW}⚠️  Some test users may already exist${NC}"
    fi
fi

cd ../infrastructure
echo ""

# Next steps
print_section "🎯 Next Steps"

echo ""
echo "1. Access the frontend application:"
echo "   ${WEBSITE_URL}"
echo ""
echo "2. Test the system:"
echo "   # Integration test suite:"
echo "   cd ../tests/integration"
echo "   python3 00_setup/test_setup.py              # Extract config from CloudFormation"
echo "   python3 run_all_tests.py                    # Run full test suite"
echo "   python3 run_all_tests.py --phase sub-agents # Test individual agents"
echo ""
echo "   # Watch streaming events:"
echo "   cd ../scripts"
echo "   python3 run_supervisor_tests.py --customer 0 --agent personalization"
echo ""
echo "3. Monitor runtime logs:"
echo "   Supervisor: aws logs tail /aws/bedrock-agentcore/runtimes/$(echo $SUPERVISOR_ARN | cut -d'/' -f2)-DEFAULT $PROFILE_FLAG --follow"
echo "   Personalization: aws logs tail /aws/bedrock-agentcore/runtimes/$(echo $PERSONALIZATION_ARN | cut -d'/' -f2)-DEFAULT $PROFILE_FLAG --follow"
echo "   Order Management: aws logs tail /aws/bedrock-agentcore/runtimes/$(echo $ORDER_MGMT_ARN | cut -d'/' -f2)-DEFAULT $PROFILE_FLAG --follow"
echo "   Product Recommendation: aws logs tail /aws/bedrock-agentcore/runtimes/$(echo $PRODUCT_REC_ARN | cut -d'/' -f2)-DEFAULT $PROFILE_FLAG --follow"
echo "   Troubleshooting: aws logs tail /aws/bedrock-agentcore/runtimes/$(echo $TROUBLESHOOTING_ARN | cut -d'/' -f2)-DEFAULT $PROFILE_FLAG --follow"
echo ""
echo "4. View CloudFront distribution:"
echo "   aws cloudfront get-distribution --id $DISTRIBUTION_ID $PROFILE_FLAG"
echo ""

print_section "✅ Deployment Complete!"
echo ""
