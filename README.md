# Guidance for Multi-Agent Orchestration using Amazon Bedrock AgentCore on AWS

## Table of Contents

1. [Overview](#overview)
    - [Cost](#cost)
2. [Prerequisites](#prerequisites)
    - [Operating System](#operating-system)
3. [Deployment Steps](#deployment-steps)
4. [Deployment Validation](#deployment-validation)
5. [Running the Guidance](#running-the-guidance)
6. [Next Steps](#next-steps)
7. [Cleanup](#cleanup)
8. [FAQ, known issues, additional considerations, and limitations](#faq-known-issues-additional-considerations-and-limitations)
9. [Notices](#notices)
10. [Authors](#authors)

## Overview

This Guidance demonstrates how to build and deploy multi-agent systems using Amazon Bedrock AgentCore and Strands Agents SDK. Traditional approaches to multi-agent systems require managing complex infrastructure, implementing custom security layers, and writing extensive orchestration code. AgentCore eliminates this complexity by providing fully-managed services for runtime, memory, identity, and observability, while Strands SDK enables developers to build agents with minimal code using Python decorators and built-in integrations.

Amazon Bedrock AgentCore is a secure, serverless runtime purpose-built for deploying and scaling dynamic AI agents using any open-source framework or model. It provides complete session isolation with dedicated microVMs per user session, scales to thousands of agent sessions in seconds, and seamlessly integrates with leading identity providers. Strands Agents SDK simplifies agent development, allowing developers to focus on agent logic rather than infrastructure concerns.

**Key Objectives:**
- Deploy agents on secure, serverless infrastructure with **AgentCore Runtime** and complete session isolation
- Transform APIs and Lambda functions into Model Context Protocol (MCP) endpoints using **AgentCore Gateway**
- Maintain both short-term and long-term context across interactions with **AgentCore Memory**
- Integrate with Amazon Cognito for secure authentication and access management using **AgentCore Identity**
- Monitor, debug, and ensure compliance with **AgentCore Observability** via OpenTelemetry and Amazon CloudWatch
- Implement multi-agent orchestration patterns with minimal code using **Strands Agents SDK** and its seamless AgentCore integration
- Provide React-based UI with session management and real-time response streaming using Server-Sent Events (SSE)
- Deploy complete infrastructure-as-code using AWS CDK

**Use Case: Intelligent Customer Support**

A customer support scenario demonstrates these AgentCore services and Strands patterns in action. A supervisor agent coordinates four specialized sub-agents, showcasing how AgentCore services work together to enable enterprise-grade multi-agent systems.

**Agents Involved:**
1. **Supervisor Agent** - Central orchestrator managing task delegation and response aggregation
2. **Personalization Agent** - Provides personalized product recommendations based on customer profiles and browsing history
3. **Order Management Agent** - Handles order status tracking, inventory queries, and order information
4. **Product Recommendation Agent** - Delivers product search and recommendations across sponsored and organic results
5. **Troubleshooting Agent** - Resolves technical issues with step-by-step guidance and FAQ support

### Architecture Diagram

![Architecture Diagram](assets/images/architecture-diagram.png)

**Architecture Flow:**

1. User authenticates via Amazon Cognito and receives JWT token
2. Frontend sends request to Supervisor Agent Runtime with JWT in Authorization header
3. AgentCore Runtime validates JWT and routes to Supervisor Agent container
4. Supervisor Agent:
   - Validates and extracts user identity from JWT
   - Retrieves customer_id from Cognito user attributes
   - Analyzes request and determines which specialized agent(s) to invoke
5. Supervisor invokes sub-agent(s) using Strands ["Agents as Tools"](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agents-as-tools/index.md) pattern with:
   - JWT in Authorization header (validated by sub-agent Runtime)
   - customer_id in payload (programmatic, not LLM-dependent)
   - **Note**: AgentCore now supports [Agent-to-Agent (A2A) protocol](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html) natively, enabling additional [Strands multi-agent patterns](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/index.md) (Graph, Swarm, Workflow)
6. Sub-Agent (built with Strands SDK):
   - AgentCore Runtime validates JWT on entry
   - Extracts JWT from request headers for Gateway authentication
   - Uses customer_id from payload for Memory/Knowledge Base queries
   - Invokes AgentCore Gateway [MCP tools](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/mcp-tools/) (JWT validated by Gateway)
7. Sub-agent returns results to Supervisor
8. Supervisor aggregates responses and streams back to user via Server-Sent Events (SSE)
9. Frontend displays response with real-time updates

**Identity & Security:**
- JWT validated at every service boundary (Runtime, Gateway)
- User identity verifiable at any point by decoding JWT
- customer_id passed programmatically to ensure data isolation
- Same JWT propagated through entire chain for end-to-end authentication

### Cost

_You are responsible for the cost of the AWS services used while running this Guidance. As of [MONTH] [YEAR], the cost for running this Guidance with the default settings in the US East (N. Virginia) Region is approximately $[X.XX] per month._

_We recommend creating a [Budget](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) through [AWS Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/) to help manage costs. Prices are subject to change. For full details, refer to the pricing webpage for each AWS service used in this Guidance._

### Sample Cost Table

The following table provides a sample cost breakdown for deploying this Guidance with the default parameters in the US East (N. Virginia) Region for one month.

<!-- TODO: Generate cost breakdown using AWS Pricing Calculator and upload PDF to BuilderSpace -->

| AWS service  | Dimensions | Cost [USD] |
| ----------- | ------------ | ------------ |
| Amazon Bedrock AgentCore | TBD | $ TBD |
| Amazon Bedrock Knowledge Bases | TBD | $ TBD |
| Amazon OpenSearch Serverless | TBD | $ TBD |
| Amazon Cognito | TBD | $ TBD |
| Amazon CloudFront | TBD | $ TBD |
| Amazon S3 | TBD | $ TBD |
| AWS Lambda | TBD | $ TBD |

## Prerequisites

### Operating System

Any operating system that supports Node.js and the required tools listed below.

### Required Tools

- **Node.js v22.x** - Install via [nvm](https://github.com/nvm-sh/nvm) for version management
- **AWS CDK CLI v2.220.0 or later** - Install globally: `npm install -g aws-cdk`
- **Python 3.13** - Required for agent runtime containers
- **AWS CLI v2** - [Installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Docker** - Required for building agent container images
- **Git** - For cloning the repository

### AWS Account Requirements

**IAM Permissions:**
- Permissions to create and manage:
  - Amazon Bedrock AgentCore resources (runtimes, memory, gateways)
  - Amazon Bedrock Knowledge Bases
  - Amazon Bedrock model invocation for:
    - `amazon.titan-embed-text-v2:0` (Knowledge Base embeddings)
    - `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Supervisor Agent)
    - `global.anthropic.claude-haiku-4-5-20251001-v1:0` (sub-agents)
  - Amazon OpenSearch Serverless collections
  - Amazon Cognito user pools
  - Amazon S3 buckets
  - Amazon CloudFront distributions
  - AWS WAF web ACLs
  - AWS Lambda functions
  - IAM roles and policies
  - Amazon ECR repositories
  - AWS KMS keys
  - AWS Systems Manager Parameter Store
  - CloudWatch Logs log groups

**Service Quotas:**
Ensure sufficient quotas for:
- Amazon Bedrock AgentCore runtimes (5 runtimes)
- Amazon Bedrock Knowledge Bases (2 knowledge bases)
- Amazon OpenSearch Serverless collections (2 collections)
- Amazon Cognito user pools (1 user pool)

### AWS CDK Bootstrap

This Guidance uses AWS CDK. The deployment script will automatically bootstrap your environment if needed. If you prefer to bootstrap manually before deployment:

```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

Replace `ACCOUNT-NUMBER` with your AWS account ID and `REGION` with your target region (e.g., `us-east-1`).

### Supported Regions

This Guidance is designed for AWS Regions where Amazon Bedrock AgentCore is available. As of publication, this includes:
- **US East (N. Virginia)** - `us-east-1`
- **US West (Oregon)** - `us-west-2`

Verify AgentCore availability in your region in the [AWS Regional Services List](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/).

## Deployment Steps

### Clone the Repository

```bash
git clone https://github.com/aws-solutions-library-samples/guidance-for-multi-agent-orchestration-using-bedrock-agentcore-on-aws.git
cd guidance-for-multi-agent-orchestration-using-bedrock-agentcore-on-aws
```

### Deploy the Complete System

The deployment script automates the entire process including infrastructure, agents, and frontend.

```bash
cd infrastructure
./deploy-complete-system.sh [PROFILE] [REGION]
```

**Arguments:**
- `PROFILE` (optional): AWS CLI profile name. Uses default profile if not specified.
- `REGION` (optional): AWS region. Uses profile's default region or `us-east-1` if not specified.

**Examples:**
```bash
# Use AWS CLI defaults
./deploy-complete-system.sh

# Use specific profile
./deploy-complete-system.sh my-profile

# Use specific profile and region (backend deploys to us-west-2, frontend to us-east-1)
./deploy-complete-system.sh my-profile us-west-2
```

**Note:** The frontend stack (CloudFront + S3) always deploys to `us-east-1` due to AWS WAF requirements for CloudFront, but is named by the backend region (e.g., `FrontendStack-us-west-2` when backend is in us-west-2) to support multiple deployments.

### What the Script Does

The deployment script performs the following steps automatically:

1. **Build CDK Infrastructure** - Compiles TypeScript CDK code
2. **Bootstrap CDK** - Bootstraps CDK in your account/region if needed
3. **Build Frontend** - Compiles React frontend application
4. **Deploy All Stacks** - Deploys infrastructure in correct order:
   - `KnowledgeBaseStack` - OpenSearch Serverless collections and Bedrock Knowledge Bases
   - `CustomerSupportAssistantStack` - Supervisor agent, Cognito, AgentCore Memory
   - `PersonalizationAgentStack` - Personalization agent runtime and gateway
   - `OrderManagementAgentStack` - Order management agent runtime and gateway
   - `ProductRecommendationAgentStack` - Product recommendation agent runtime and gateway
   - `TroubleshootingAgentStack` - Troubleshooting agent runtime and gateway
   - `FrontendStack-{backend-region}` - S3 bucket, CloudFront distribution, WAF (always deployed to us-east-1, named by backend region)
5. **Configure Frontend** - Updates frontend with stack outputs (runtime ARNs, Cognito IDs)
6. **Upload Frontend** - Deploys built frontend to S3
7. **Invalidate CloudFront** - Clears CloudFront cache for immediate availability
8. **Configure Authorization** - Sets up runtime authorization headers for agent communication
9. **Create Test Users** - Creates sample users in Cognito for testing

### Deployment Time

**Estimated total deployment time:**
- **First deployment (x86 machines):** 30-35 minutes
- **First deployment (ARM machines):** 20-25 minutes
- **Subsequent deployments:** 10-15 minutes (with cached Docker images)

**Note:** Docker images must be built for ARM64 architecture because Amazon Bedrock AgentCore Runtime runs on ARM64 infrastructure. On x86 machines, Docker must emulate ARM64, which significantly increases build time. ARM machines (like Apple Silicon Macs or AWS Graviton instances) build natively and are much faster.

Breakdown:
- Docker image builds for 5 agents: 15-20 minutes (x86 with emulation), 5-10 minutes (ARM native) - first time only
- CDK infrastructure deployment: 10-15 minutes
- Frontend build and upload: 3-5 minutes
- Configuration and validation: 2-3 minutes

Subsequent deployments are faster due to Docker layer caching reducing build time and emulation overhead.

## Deployment Validation

The deployment script validates all components and displays a comprehensive summary confirming successful deployment:

- **Website URL** - CloudFront distribution URL to access the application
- **Test Credentials** - Pre-configured user accounts and passwords for signing in
- **Cognito Configuration** - User Pool ID and Client ID for authentication
- **Runtime ARNs** - AgentCore Runtime identifiers for all agents
- **Knowledge Base IDs** - Bedrock Knowledge Base identifiers
- **Monitoring Commands** - Ready-to-use commands for viewing runtime logs
- **Testing Commands** - Commands to run integration tests

All outputs are saved to `infrastructure/deployment-outputs.json` for reference.

### Monitor Runtime Logs

The "Next Steps" section in the deployment output provides ready-to-use commands for monitoring each agent runtime in real-time. Simply copy and run these commands to tail logs for:
- Supervisor agent
- Personalization agent
- Order Management agent
- Product Recommendation agent
- Troubleshooting agent

**Note:** AgentCore logs include OpenTelemetry (OTEL) telemetry data which can be verbose. To view agent interactions in a more readable format, use the log analysis script:

```bash
# View supervisor agent logs (last 30 minutes - default)
python3 scripts/show_agent_logs.py supervisor

# View personalization agent logs (last 60 minutes)
python3 scripts/show_agent_logs.py personalization --minutes 60

# Specify AWS profile if not using default
python3 scripts/show_agent_logs.py supervisor --profile <your-profile>

# Other agents: order-management, product-recommendation, troubleshooting
```

The script filters OTEL telemetry and displays:
- Agent reasoning and responses
- Tool calls with parameters and results
- Long-term memories retrieved from AgentCore Memory
- Timeline of agent interactions

### Test the Application

1. Open the **Website URL** from the summary
2. Sign in using any test user **email as the username** and the password shown in the output
3. Send a test message to verify the system responds

### Optional: Run Integration Tests

For comprehensive validation of all deployed components:

```bash
# First time only: Extract configuration from deployed stacks
python3 tests/integration/00_setup/test_setup.py

# Run all integration tests
python3 tests/integration/run_all_tests.py
```

See [tests/integration/README.md](tests/integration/README.md) for detailed test documentation and individual test execution options.

## Running the Guidance

### Accessing the Frontend

1. After deployment completes, the CloudFront distribution URL will be displayed in the output
2. Navigate to the URL in your web browser
3. Sign in with any test user email as the username (e.g., `mateo_jackson@example.com`) and the password from the deployment output

### Example Conversation

**Login as:** `carlos_salazar@example.com` (cust003)

This conversation demonstrates multi-agent orchestration where the Supervisor delegates to specialized agents based on the user's needs:

**User:** "I ordered a ProMax Laptop recently. Can you check my order status?"

*Agent behavior:* Supervisor → **Order Management Agent** queries order o003 for cust003  
*Response example:* "Your ProMax Laptop order (o003) was delivered on 10/25/24. I see it shows a return status. Would you like help with that?"

---

**User:** "Yes, I returned it because it was overheating. Can you help me understand what was wrong?"

*Agent behavior:* Supervisor → **Troubleshooting Agent** queries Knowledge Base for ProMax Laptop overheating issues  
*Response example:* "Overheating in the ProMax Laptop can be caused by poor ventilation or heavy use. I recommend ensuring proper ventilation, using a cooling pad, and keeping software updated. Would you like more detailed troubleshooting steps?"

---

**User:** "I see. What other laptops would you recommend for me?"

*Agent behavior:* Supervisor → **Personalization Agent** retrieves customer profile (cust003: 24 years old, prefers computers, low price range, bronze tier) → **Product Recommendation Agent** suggests alternatives  
*Response example:* "Based on your preferences for computers in a lower price range, I'd recommend the UltraBook Air or FlexTab Convertible. Both offer good performance within your budget."

---

**User:** "Is the UltraBook Air in stock?"

*Agent behavior:* Supervisor → **Order Management Agent** checks inventory  
*Response example:* "Yes, the UltraBook Air is currently in stock with 15 units available."

### Monitoring Agent Activity

Use the log monitoring commands from the deployment output to watch agent interactions in real-time as the conversation progresses.

### Experiment with Different Test Users

Try logging in as different test users to see how the system provides personalized responses based on customer profiles:

- **mateo_jackson@example.com** (cust001) - 28 years old, high income, prefers computers, gold tier
- **martha_rivera@example.com** (cust002) - 32 years old, medium income, prefers watches, silver tier  
- **carlos_salazar@example.com** (cust003) - 24 years old, low income, prefers computers, bronze tier
- **richard_roe@example.com** (cust004) - 45 years old, high income, prefers computers, platinum tier

Each user has different order history, browsing patterns, and preferences that influence agent responses. See `test_users_config-{region}.json` in the scripts directory for the complete list of 10 test users and their shared password.

### Monitor Agent Activity and Reasoning

Use the log monitoring commands from the deployment output to observe the complete agent orchestration flow:

**Supervisor Agent Logs:**
- **Agentic reasoning**: See how the supervisor analyzes user queries and decides which specialized agents to invoke
- **Agent-as-Tool invocations**: This system uses Strands "Agents as Tools" pattern where specialized agents are wrapped as callable tools. Watch the supervisor invoke sub-agents like functions
- **Memory retrieval**: Observe when the supervisor queries long-term memory for facts and preferences extracted from previous conversations
- **Response aggregation**: See how the supervisor combines results from multiple specialized agents into cohesive responses

**Sub-Agent Logs:**
- **Agentic reasoning**: Watch each sub-agent analyze its delegated task and determine which tools to use
- **MCP tool invocations**: See sub-agents call AgentCore Gateway tools (Model Context Protocol endpoints) to access data sources
- **Order Management Agent**: Queries to orders and inventory databases via Gateway
- **Personalization Agent**: Customer profile lookups and browsing history retrieval from Knowledge Base via Gateway
- **Product Recommendation Agent**: Sponsored vs organic product searches via Gateway
- **Troubleshooting Agent**: FAQ and troubleshooting guide queries from Knowledge Base via Gateway

The logs show the complete flow: agentic reasoning, tool selection decisions, MCP tool invocations with parameters, and results returned. This visibility into each agent's decision-making process helps understand how the multi-agent system collaborates to solve complex queries.

**Analyze logs with the performance script:**

```bash
# Analyze supervisor agent (last 30 minutes)
python3 ../scripts/analyze_agent_performance.py supervisor --profile <your-profile>

# Other agents: personalization, order-management, product-recommendation, troubleshooting
```

The script makes analyzing CloudWatch logs easier by showing user messages, agent reasoning, tool calls with parameters, and results in chronological order.

### Experience AgentCore Memory

AgentCore Memory automatically becomes more valuable with continued interaction. The system uses a two-tier memory architecture:

**Short-Term Memory (STM):**
- Stores conversation history for the current session
- Automatically saved as you interact with agents
- Retrieved to maintain context within a conversation
- Provides current-session context to agents

**Long-Term Memory (LTM):**
- AgentCore automatically extracts facts and preferences from conversations in the background
- Facts and preferences are stored across sessions
- Uses semantic search to retrieve relevant memories based on natural language queries
- Provides cross-session context about users

**Memory Integration with Strands:**

This guidance demonstrates how Strands SDK simplifies AgentCore Memory integration through `AgentCoreMemorySessionManager`. To showcase different configuration options, agents are configured with varying memory capabilities:

- **All agents with memory** (Supervisor, Personalization, Troubleshooting) use `AgentCoreMemorySessionManager` to automatically manage short-term memory (current session context) and contribute their conversations to the shared memory resource
- **Supervisor agent** is additionally configured with `retrieval_config` to retrieve long-term facts and preferences (cross-session context), injecting them into its context via `<user_context>` blocks
- **Sub-agents** (Personalization, Troubleshooting) contribute to memory through their conversations but don't retrieve long-term memories - they rely on the supervisor for cross-session context while maintaining their own current-session context through STM

This configuration demonstrates one approach: centralized LTM retrieval through the supervisor with distributed STM across agents. Your implementation may benefit from different configurations depending on your use case - for example, sub-agents could also retrieve LTM directly for more autonomous operation.

After having several conversations as a single user, run the analysis script again to see the **LONG-TERM MEMORY ACCUMULATED** section showing facts and preferences the system has learned. These are extracted from `<user_context>` blocks in supervisor logs, generated by AgentCore Memory's `semanticMemoryStrategy` and `userPreferenceMemoryStrategy`.

## Next Steps

### Customize the Guidance

Extend this guidance for your specific requirements:

- **Add specialized agents**: Create new agents for domain-specific tasks (billing, shipping, returns)
- **Integrate your data**: Replace sample data with your product catalog, customer database, and knowledge base
- **Customize agent prompts**: Modify system prompts in `agents/*/system_prompt.py` to match your brand voice
- **Tune memory strategies**: Adjust memory extraction patterns in `infrastructure/lambda/memory-manager/index.py`
- **Add authentication providers**: Integrate with your existing identity provider beyond Cognito
- **Enhance the frontend**: Customize the React UI in `frontend/src/` for your branding and features

## Cleanup

To remove all resources created by this Guidance:

```bash
cd infrastructure
./cleanup.sh [PROFILE]
```

**Arguments:**
- `PROFILE` (optional): AWS CLI profile name. Uses default profile if not specified.

The cleanup script detects the region from your environment (`AWS_REGION`), profile configuration, or defaults to `us-east-1`.

**Cleanup Options:**

**Local Files Only (Options 1-4):**
- Clean up generated configuration files, build artifacts, and test user data
- **Note:** Deleting test user config will cause the deployment script to regenerate test users with new passwords on the next deployment

**AWS Stacks + Local Files:**
- **Option 5**: Destroy all stacks except Knowledge Base - Removes agents while preserving Knowledge Base data for future deployments
- **Option 6**: Destroy all stacks including Knowledge Base - Complete cleanup of all AWS resources

**Note:** Options 5 and 6 automatically clean up local files and handle region-specific resources including test user configuration files (`test_users_config-{region}.json`) and frontend stacks in us-east-1.

## FAQ, known issues, additional considerations, and limitations

### FAQ

**Q: I'm getting errors from Bedrock for these models**

This Guidance uses Amazon Bedrock inference profiles for Claude models:
- Regional: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Supervisor Agent)
- Global: `global.anthropic.claude-haiku-4-5-20251001-v1:0` (sub-agents)

Before deployment, ensure you have cross-region inference access configured for global inference profiles.

See:
- [Amazon Bedrock model access documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [Global cross-Region inference documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html)
- [Enable cross-Region inference in multi-account environments](https://aws.amazon.com/blogs/machine-learning/enable-amazon-bedrock-cross-region-inference-in-multi-account-environments/)

**Q: How do I enable AgentCore observability and tracing?**

To enable full AgentCore observability features including trace visualization and performance monitoring, CloudWatch Transaction Search must be configured as a one-time setup per AWS account.

This enables:
- Trace visualization in CloudWatch GenAI Observability dashboard
- Agent performance monitoring and debugging  
- Distributed tracing across AgentCore resources (runtime, memory, gateway)

See [AgentCore Observability Configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html) for setup instructions.

**Q: Why does Docker build take so long?**

Docker builds for ARM64 architecture may take 15-20 minutes on x86 machines (with emulation) or 5-10 minutes on ARM machines (native) on first deployment. This is because Amazon Bedrock AgentCore Runtime runs on ARM64 infrastructure.

**Q: What are the ongoing costs for this Guidance?**

This Guidance creates Amazon Bedrock AgentCore runtimes that are billed based on usage. Test users are created in Amazon Cognito for demonstration purposes.

For any feedback, questions, or suggestions, please use the issues tab under this repo.

## Notices

*Customers are responsible for making their own independent assessment of the information in this Guidance. This Guidance: (a) is for informational purposes only, (b) represents AWS current product offerings and practices, which are subject to change without notice, and (c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. AWS responsibilities and liabilities to its customers are controlled by AWS agreements, and this Guidance is not part of, nor does it modify, any agreement between AWS and its customers.*

## Authors

- Sreedevi Velagala
- Robert Fisher
- Mahender Reddy
- Xinyu Qu
- Rajat Jain
- Daniel Wells
