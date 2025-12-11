# Product Recommendation Agent

A specialized AI agent that provides personalized product recommendations by combining sponsored and organic product data through AgentCore Gateway integration.

## Overview

The Product Recommendation Agent is part of a multi-agent customer support system. It uses AWS Bedrock AgentCore Runtime with MCP (Model Context Protocol) to access product data from two separate Lambda functions via AgentCore Gateways.

### Key Features

- **Dual Product Sources**: Combines sponsored products (paid placements) with organic products (popularity-based)
- **Intelligent Recommendations**: Uses Claude 3.7 Sonnet to understand customer intent and provide relevant suggestions
- **Memory Persistence**: Maintains conversation history across sessions using AgentCore Memory
- **Structured Output**: Returns JSON responses with product details, ratings, prices, and summaries
- **Category Filtering**: Supports filtering by product categories (smartphones, laptops, headphones, etc.)
- **Custom Quantities**: Handles requests for specific numbers of products and sponsored/organic ratios

## Architecture

```
User Request (JWT Token)
  ↓
AgentCore Runtime (validates JWT, passes Authorization header)
  ↓
Product Recommendation Agent (extracts token from context.request_headers)
  ↓
MCP Clients (authenticate with token)
  ↓
AgentCore Gateways (2 gateways: sponsored-products, organic-products)
  ↓
Lambda Functions (query SQLite databases)
  ↓
Product Data (returned to agent)
  ↓
Agent (uses Strands to process and format)
  ↓
Structured JSON Response (sponsored + organic products)
```

### Components

1. **Agent Container** (`agent.py`)
   - Runs in AWS Fargate with ARM64 architecture
   - Uses Strands framework for agent orchestration
   - Implements memory hooks for conversation persistence
   - Extracts JWT token from request context
   - Creates MCP clients for both gateways

2. **AgentCore Gateways** (2 gateways)
   - **Sponsored Products Gateway**: Routes to sponsored products Lambda
   - **Organic Products Gateway**: Routes to organic products Lambda
   - Both use Cognito JWT authentication
   - Expose tools via MCP protocol

3. **Lambda Functions** (2 functions)
   - **Sponsored Products Lambda**: Manages 20 sponsored products with priority/tier data
   - **Organic Products Lambda**: Manages 25 organic products with popularity scores
   - Both use SQLite databases in `/tmp/` directory
   - Support filtering by category, price, rating, stock status

4. **Memory System**
   - Uses AgentCore Memory for conversation history
   - Loads last 5 conversation turns on agent initialization
   - Automatically saves new messages after each interaction
   - Enables context-aware recommendations across sessions

## Data Model

### Sponsored Products
```json
{
  "product_id": "SP001",
  "name": "ProMax Laptop",
  "description": "High-performance laptop for professionals",
  "category": "laptop",
  "rating": 4.9,
  "review_count": 2500,
  "price": 1899.99,
  "source": "sponsored",
  "sponsor_company": "TechCorp",
  "priority": 1,
  "sponsor_tier": "platinum"
}
```

### Organic Products
```json
{
  "product_id": "OP001",
  "name": "BudsPro Plus",
  "description": "Premium wireless earbuds",
  "category": "headphones",
  "rating": 4.5,
  "review_count": 15000,
  "price": 149.99,
  "source": "organic",
  "units_sold": 45000,
  "popularity_score": 8.7,
  "in_stock": "Yes"
}
```

### Response Format
```json
{
  "sponsored_products": [...],
  "organic_products": [...],
  "summary": "Natural language summary of recommendations",
  "total_products": 5
}
```

## Deployment

### Prerequisites
- AWS CDK 2.217.0+
- Docker (for building ARM64 container images)
- Python 3.11+
- Node.js 18+
- AWS credentials configured

### Deployment Steps

```bash
# 1. Build and deploy the stack
cd infrastructure
npm install
npm run build
npx cdk deploy ProductRecommendationAgentStack --require-approval never

# 2. CRITICAL: Apply header configuration fix
# This step is REQUIRED after every deployment because CloudFormation
# doesn't preserve the requestHeaderConfiguration setting
cd ..
python3 scripts/fix_runtime_auth.py \
  "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/RUNTIME_ID" \
  --region us-east-1

# 3. Test the agent
python3 test_product_recommendation_agent.py
```

### Why the Header Fix is Required

The CDK stack includes `requestHeaderConfiguration` to allow the Authorization header to be passed to the agent:

```typescript
requestHeaderConfiguration: {
  requestHeaderAllowlist: ['Authorization']
}
```

However, CloudFormation doesn't actually apply this configuration. The `fix_runtime_auth.py` script manually updates the runtime via the `bedrock-agentcore-control` API to enable header propagation.

**Important**: You must run the fix script after every deployment that updates the runtime, or the agent won't be able to authenticate with the gateways.

## Testing

### Test Script

The `test_product_recommendation_agent.py` script provides comprehensive testing:

```bash
python3 test_product_recommendation_agent.py
```

### Test Cases

1. **Default Recommendations**: Requests general product recommendations (expects 2 sponsored + 3 organic)
2. **Category-Specific**: Requests products from a specific category (e.g., smartphones)
3. **Custom Quantity**: Requests specific numbers of products with custom sponsored/organic ratios

### Expected Output

```
================================================================================
TEST SUMMARY
================================================================================
✅ PASS: Default Recommendations
✅ PASS: Category-Specific
✅ PASS: Custom Quantity

Total: 3/3 tests passed
================================================================================

🎉 ALL TESTS PASSED! Product Recommendation Agent is working correctly!
```

### Debugging

Check CloudWatch logs if tests fail:

```bash
# Agent logs
aws logs tail /aws/agentcore/product-recommendation-agent --follow --region us-east-1

# Runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes/RUNTIME_ID-DEFAULT --follow --region us-east-1

# Lambda logs (sponsored products)
aws logs tail /aws/lambda/ProductRecommendationAgen-SponsoredProductsLambda --follow --region us-east-1

# Lambda logs (organic products)
aws logs tail /aws/lambda/ProductRecommendationAgen-OrganicProductsLambda --follow --region us-east-1
```

## Configuration

### Environment Variables

The agent container receives these environment variables from the CDK stack:

- `SPONSORED_GATEWAY_ID`: Gateway ID for sponsored products
- `ORGANIC_GATEWAY_ID`: Gateway ID for organic products
- `MEMORY_ID`: AgentCore Memory ID for conversation history
- `AWS_REGION`: AWS region (default: us-east-1)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

### Authentication

The agent uses Cognito User Pool for authentication:

1. User authenticates with Cognito to get JWT access token
2. Token is passed in `Authorization: Bearer <token>` header
3. AgentCore Runtime validates token via Cognito OIDC discovery
4. Runtime passes token to agent via `context.request_headers`
5. Agent extracts token and uses it to authenticate with MCP Gateways

## Implementation Details

### Memory Hooks

The agent implements two memory hooks:

1. **on_agent_initialized**: Loads last 5 conversation turns when agent starts
2. **on_message_added**: Saves new messages to memory after each interaction

```python
class MemoryHookProvider(HookProvider):
    def on_agent_initialized(self, event: AgentInitializedEvent):
        # Load recent conversation history
        recent_turns = self.memory_client.get_last_k_turns(
            memory_id=self.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=5
        )
        # Append to system prompt
        event.agent.system_prompt += f"\n\nRecent conversation:\n{context}"
    
    def on_message_added(self, event: MessageAddedEvent):
        # Save message to memory
        self.memory_client.create_event(
            memory_id=self.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[(text, role)]
        )
```

### MCP Gateway Integration

The agent creates two MCP clients, one for each gateway:

```python
# Create transport with authentication
def create_streamable_http_transport(mcp_url: str, access_token: str):
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})

# Create MCP clients
sponsored_mcp_client = MCPClient(lambda: create_streamable_http_transport(sponsored_gateway_url, access_token))
organic_mcp_client = MCPClient(lambda: create_streamable_http_transport(organic_gateway_url, access_token))

# Discover tools from both gateways
with sponsored_mcp_client, organic_mcp_client:
    sponsored_tools = get_full_tools_list(sponsored_mcp_client)
    organic_tools = get_full_tools_list(organic_mcp_client)
    tools = sponsored_tools + organic_tools
```

### Response Format

The agent returns natural language responses with product recommendations:

```python
# Agent processes the query and returns a response
agent_response = agent(conversation_context)
# Returns: Natural language text with product recommendations
```

The agent uses its tools to query both sponsored and organic product catalogs, then synthesizes the results into a comprehensive recommendation response.

## Troubleshooting

### Agent Not Responding

**Symptom**: Requests timeout with no response

**Possible Causes**:
1. Session ID too short (must be 33+ characters)
2. Container not starting (check CloudWatch logs)
3. Authorization header not configured (run fix_runtime_auth.py)

**Solution**:
```python
# Use UUID for session IDs
import uuid
session_id = str(uuid.uuid4())  # 36 characters
```

### Authorization Header Not Accessible

**Symptom**: Agent returns "Error: No Authorization header found"

**Cause**: The `requestHeaderConfiguration` wasn't applied to the runtime

**Solution**:
```bash
python3 scripts/fix_runtime_auth.py "<RUNTIME_ARN>" --region us-east-1
```

### Gateway Tools Not Working

**Symptom**: Agent returns empty product arrays

**Possible Causes**:
1. Authorization header not accessible (see above)
2. Gateway IDs incorrect in environment variables
3. Lambda functions not deployed
4. MCP client authentication failing

**Solution**:
1. Verify header configuration is applied
2. Check CloudWatch logs for MCP client errors
3. Test Lambda functions directly
4. Verify gateway IDs match deployed resources

### Memory Not Persisting

**Symptom**: Agent doesn't remember previous conversations

**Possible Causes**:
1. Memory ID not set in environment variables
2. actor_id or session_id missing from agent state
3. Memory hooks not registered

**Solution**:
1. Verify MEMORY_ID environment variable is set
2. Check agent state includes both actor_id and session_id
3. Review memory hook logs in CloudWatch

## Product Data

### Categories
- **smartphone**: 4 sponsored + 5 organic products
- **laptop**: 4 sponsored + 5 organic products
- **smartwatch**: 4 sponsored + 5 organic products
- **speaker**: 4 sponsored + 5 organic products
- **headphones**: 4 sponsored + 5 organic products

### Sponsored Product Tiers
- **Platinum**: Priority 1-2 (highest visibility)
- **Gold**: Priority 3-5
- **Silver**: Priority 6-8
- **Bronze**: Priority 9-10

### Popularity Scoring (Organic Products)
```python
popularity_score = (rating * 0.3) + (log(review_count + 1) * 0.3) + (log(units_sold + 1) * 0.4)
```

## Files

- `agent.py`: Main agent implementation
- `system_prompt.py`: Agent system prompt with instructions
- `cloudwatch_logger.py`: CloudWatch logging configuration
- `Dockerfile`: Container image definition
- `gateway/lambdas/sponsored-products/lambda_function.py`: Sponsored products Lambda
- `gateway/lambdas/organic-products/lambda_function.py`: Organic products Lambda
- `gateway/schemas/sponsored-products-tools.json`: Sponsored products tool schema
- `gateway/schemas/organic-products-tools.json`: Organic products tool schema
- `gateway/infrastructure/gateway_provider.py`: CDK construct for gateway creation

## Related Documentation

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Strands Framework](https://github.com/awslabs/strands)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Project Structure](../../.kiro/steering/structure.md)
- [Technology Stack](../../.kiro/steering/tech.md)
