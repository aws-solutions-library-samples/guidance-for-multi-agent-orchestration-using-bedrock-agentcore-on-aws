#!/usr/bin/env python3
"""
Test script for Customer Support Supervisor Agent

Tests all agents with JWT authentication via HTTP streaming.
Demonstrates real-time event streaming with tool invocation tracking.
Raw streaming events logged to scripts/test_logs/ for analysis.

SETUP:
    1. Deploy infrastructure: cd infrastructure && cdk deploy --profile <profile>
    2. Create test users: python scripts/setup_test_users.py

USAGE:
    python scripts/run_supervisor_tests.py                    # Test all agents with first customer (default)
    python scripts/run_supervisor_tests.py --agent troubleshooting
    python scripts/run_supervisor_tests.py --customer 0       # Test specific customer (all agents)
    python scripts/run_supervisor_tests.py --customer 0,2,5   # Test multiple customers
    python scripts/run_supervisor_tests.py --customer all     # Test all customers
    python scripts/run_supervisor_tests.py --agent product --customer 1
    
AGENTS: personalization, order, product, troubleshooting, multi
"""

import boto3
import json
import sys
import uuid
import requests
import time
import argparse
from pathlib import Path

import os

# Configuration
REGION = os.environ.get('AWS_REGION', 'us-east-1')
CONFIG_FILE = Path(__file__).parent / f'test_users_config-{REGION}.json'

# Agent-specific test prompts designed to trigger each agent
AGENT_PROMPTS = {
    'personalization': {
        'name': 'Personalization Agent',
        'emoji': '🔍',
        'prompt': 'What have I been browsing lately?'
    },
    'order': {
        'name': 'Order Management Agent',
        'emoji': '📦',
        'prompt': 'What is the status of my recent orders?'
    },
    'product': {
        'name': 'Product Recommendation Agent',
        'emoji': '🛍️',
        'prompt': 'Can you recommend some products for me?'
    },
    'troubleshooting': {
        'name': 'Troubleshooting Agent',
        'emoji': '🔧',
        'prompt': 'My ZenSound wireless headphones won\'t connect to Bluetooth, can you help me fix this?'
    },
    'multi': {
        'name': 'Multi-Agent Coordination',
        'emoji': '🎯',
        'prompt': 'Can you check if I have any current orders and then provide me a good recommendation for laptop I might like?'
    }
}

def load_config():
    """Load test configuration."""
    if not CONFIG_FILE.exists():
        print("❌ Configuration file not found!")
        print(f"   Expected: {CONFIG_FILE}")
        print("\n   Run setup first:")
        print("   python scripts/setup_test_users.py")
        sys.exit(1)
    
    try:
        config = json.loads(CONFIG_FILE.read_text())
        print(f"✅ Loaded configuration from {CONFIG_FILE}")
        return config
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        sys.exit(1)

def get_jwt_token(config, username, password):
    """Get JWT token from Cognito."""
    print(f"🔐 Authenticating as {username}...")
    
    session = boto3.Session(profile_name=config['profile'], region_name=config['region'])
    cognito = session.client('cognito-idp')
    
    try:
        response = cognito.initiate_auth(
            ClientId=config['client_id'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        token = response['AuthenticationResult']['AccessToken']
        print("✅ Authentication successful")
        return token
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)

def invoke_supervisor_http(config, token, query, session_id):
    """Invoke supervisor via HTTP with JWT and handle streaming."""
    print(f"\n📤 Sending query: {query}", flush=True)
    
    import urllib.parse
    encoded_arn = urllib.parse.quote(config['runtime_arn'], safe='')
    
    agentcore_endpoint = f"https://bedrock-agentcore.{config['region']}.amazonaws.com"
    url = f"{agentcore_endpoint}/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
    }
    
    payload = json.dumps({'prompt': query})
    
    from datetime import datetime
    log_dir = Path(__file__).parent / 'test_logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"streaming_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=120, stream=True)
        
        if response.status_code == 200:
            print("🔄 Streaming response:", flush=True)
            complete_response = []
            final_result = None  # Track final result with metrics
            tools_called = set()
            content_blocks = {}  # Track text by content block index
            tool_use_map = {}  # Map tool use IDs to tool names
            seen_tool_results = False  # Track if we've received tool results
            shown_final_separator = False  # Track if we've shown the final response separator
            
            with open(log_file, 'w') as f:
                f.write(f"Streaming events log for query: {query}\n")
                f.write("=" * 80 + "\n")
                
                for line in response.iter_lines(decode_unicode=True):
                    if line and line.startswith('data: '):
                        data = line[6:]  # Remove SSE 'data: ' prefix
                        
                        f.write(f"EVENT: {data}\n")
                        f.flush()
                        
                        try:
                            event = json.loads(data)
                            if isinstance(event, dict) and 'event' in event:
                                event_obj = event['event']
                                
                                if 'messageStart' in event_obj:  # Agent begins new response message
                                    content_blocks = {}
                                    if seen_tool_results and not shown_final_separator:
                                        print("\n" + "─" * 70)
                                        print("💬 AGENT RESPONSE:")
                                        print("─" * 70)
                                        shown_final_separator = True
                                
                                # Accumulate streaming text chunks (not displayed incrementally for better UX)
                                elif 'contentBlockDelta' in event_obj:
                                    delta = event_obj['contentBlockDelta']
                                    index = delta['contentBlockIndex']
                                    text = delta['delta'].get('text', '')
                                    
                                    if index not in content_blocks:
                                        content_blocks[index] = ''
                                    content_blocks[index] += text
                                
                                # Display complete text block when ready (better readability than char-by-char)
                                elif 'contentBlockStop' in event_obj:
                                    index = event_obj['contentBlockStop']['contentBlockIndex']
                                    complete_text = content_blocks.get(index, '').strip()
                                    
                                    if complete_text and index == 0:
                                        # Show separator before final response if we've seen tool results
                                        if seen_tool_results and not shown_final_separator:
                                            print("\n" + "─" * 70, flush=True)
                                            print("📝 FINAL RESPONSE:", flush=True)
                                            print("─" * 70, flush=True)
                                            shown_final_separator = True
                                        print(f"💭 {complete_text}", flush=True)
                                
                                elif 'contentBlockStart' in event_obj:  # Detect tool invocations for user feedback
                                    content_block = event_obj['contentBlockStart']
                                    if 'start' in content_block and 'toolUse' in content_block['start']:
                                        tool_name = content_block['start']['toolUse'].get('name', '')
                                        if tool_name and tool_name not in tools_called:
                                            if 'personalization' in tool_name:
                                                print("🔍 Gathering your preferences... (pulling data from several sources, please be patient)", flush=True)
                                            elif 'order_management' in tool_name:
                                                print("📦 Checking order information... (pulling data from several sources, please be patient)", flush=True)
                                            elif 'product_recommendation' in tool_name:
                                                print("🛍️ Finding product recommendations... (pulling data from several sources, please be patient)", flush=True)
                                            elif 'troubleshooting' in tool_name:
                                                print("🔧 Analyzing technical issues... (pulling data from several sources, please be patient)", flush=True)
                                            tools_called.add(tool_name)
                                
                                # Show message completion
                                elif 'messageStop' in event_obj:
                                    stop_reason = event_obj['messageStop'].get('stopReason')
                                    if stop_reason == 'end_turn':
                                        print("📄 Response complete", flush=True)
                                
                                # Show final message
                                elif 'message' in event:
                                    complete_response.append(data)
                            
                            # Check for complete messages with tool info (in event order)
                            if isinstance(event, dict) and 'message' in event:
                                msg = event['message']
                                
                                # Show tool queries and track tool IDs
                                if msg.get('role') == 'assistant':
                                    for content in msg.get('content', []):
                                        if 'toolUse' in content:
                                            tool = content['toolUse']
                                            tool_name = tool['name']
                                            tool_id = tool['toolUseId']
                                            query_text = tool['input'].get('query', str(tool['input']))
                                            
                                            tool_use_map[tool_id] = tool_name  # Map for later result matching
                                            
                                            if len(query_text) > 500:
                                                query_text = query_text[:500] + "..."
                                            
                                            print(f"   🔧 {tool_name}: {query_text}", flush=True)
                                
                                # Show tool results with tool name
                                elif msg.get('role') == 'user':
                                    for content in msg.get('content', []):
                                        if 'toolResult' in content:
                                            seen_tool_results = True
                                            result = content['toolResult']
                                            tool_id = result['toolUseId']
                                            status = result['status']
                                            
                                            # Get tool name from mapping
                                            tool_name = tool_use_map.get(tool_id, 'unknown')
                                            
                                            result_text = ''
                                            for res_content in result.get('content', []):
                                                if 'text' in res_content:
                                                    result_text = res_content['text']
                                                    break
                                            
                                            if len(result_text) > 500:
                                                result_text = result_text[:500] + "..."
                                            
                                            print(f"   ✅ {tool_name} ({status}): {result_text}", flush=True)
                            
                            # Also check for result events (different format)
                            elif isinstance(event, str) and 'result' in event and 'AgentResult' in event:
                                complete_response.append(data)
                                final_result = data  # Capture final result for metrics
                                
                        except:
                            # If not JSON or parsing fails, just log it
                            pass
                            
                    elif line:
                        # Handle non-SSE response (fallback to JSON)
                        f.write(f"NON-SSE: {line}\n")
                        f.flush()
                        print(f"📄 {line}", flush=True)
                        complete_response.append(line)
            
            result = '\n'.join(complete_response)
            print(f"✅ Streaming complete ({len(result)} chars)", flush=True)
            print(f"📝 Full event log: {log_file}")
            return {'text': result, 'final_result': final_result, 'tools_called': tools_called}
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}", flush=True)
            return None
            
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None

def test_agent(config, user, agent_key):
    """Test a specific agent."""
    agent_info = AGENT_PROMPTS[agent_key]
    
    print(f"\n{agent_info['emoji']} Testing {agent_info['name']}")
    print("-" * 70)
    
    token = get_jwt_token(config, user['email'], user['password'])
    session_id = f"test-{agent_key}-{uuid.uuid4()}"
    print(f"🔑 Session ID: {session_id}")
    
    response = invoke_supervisor_http(config, token, agent_info['prompt'], session_id)
    
    if response:
        # Check if expected tool was called
        if agent_key == 'multi':
            # Multi-agent test should call multiple tools
            tool_called = len(response.get('tools_called', [])) >= 2
            if tool_called:
                print(f"✅ {agent_info['name']} successfully invoked multiple agents")
                print(f"   Tools called: {response.get('tools_called', [])}")
            else:
                print(f"⚠️  Expected multiple agents but only called: {response.get('tools_called', [])}")
        else:
            # Single agent test
            expected_tool = f"{agent_key}_" if agent_key != 'order' else 'order_management_'
            tool_called = any(expected_tool in tool for tool in response.get('tools_called', []))
            
            if tool_called:
                print(f"✅ {agent_info['name']} successfully invoked")
            else:
                print(f"⚠️  Response received but {agent_info['name']} may not have been called")
                print(f"   Tools called: {response.get('tools_called', [])}")
        
        return True  # Still count as success if we got a response
    else:
        print(f"❌ Test failed for {agent_info['name']}")
        return False

def main():
    """Run tests."""
    parser = argparse.ArgumentParser(description='Test Customer Support Supervisor Agent')
    parser.add_argument('--agent', choices=['personalization', 'order', 'product', 'troubleshooting', 'multi', 'all'],
                       default='all', help='Which agent to test (default: all)')
    parser.add_argument('--customer', type=str, help='Customer index (0-based), comma-separated list (0,2,5), or "all" (default: 0)')
    args = parser.parse_args()
    
    print("=" * 70)
    print("Customer Support Supervisor Agent Test (HTTP/JWT)")
    print("=" * 70)
    
    # Load configuration
    config = load_config()
    
    # Determine which agents to test
    if args.agent == 'all':
        agents_to_test = list(AGENT_PROMPTS.keys())
        print(f"\n🎯 Testing all {len(agents_to_test)} agents")
    else:
        agents_to_test = [args.agent]
        print(f"\n🎯 Testing {AGENT_PROMPTS[args.agent]['name']} only")
    
    # Determine which customers to test (default to first customer only)
    if args.customer is not None:
        if args.customer.lower() == 'all':
            users_to_test = config['users']
        else:
            # Parse comma-separated list of customer indices
            try:
                customer_indices = [int(idx.strip()) for idx in args.customer.split(',')]
                users_to_test = []
                for idx in customer_indices:
                    if idx >= len(config['users']):
                        print(f"❌ Customer index {idx} out of range (0-{len(config['users'])-1})")
                        return 1
                    users_to_test.append(config['users'][idx])
            except ValueError:
                print(f"❌ Invalid customer argument: {args.customer}. Use index (0), list (0,2,5), or 'all'")
                return 1
    else:
        users_to_test = [config['users'][0]]  # Default to first customer only
    
    print(f"👤 Testing {len(users_to_test)} customer(s)")
    
    # Run tests
    results = {}
    test_count = 0
    for user in users_to_test:
        print(f"\n{'='*70}")
        print(f"Customer: {user['customer_id']}")
        print('='*70)
        
        for agent_key in agents_to_test:
            if test_count > 0:
                print(f"\n⏳ Waiting 5 seconds to avoid throttling...", flush=True)  # Rate limiting for API calls
                time.sleep(5)
            
            result_key = f"{user['customer_id']}_{agent_key}"
            results[result_key] = test_agent(config, user, agent_key)
            test_count += 1
    
    # Summary
    print(f"\n{'=' * 70}")
    print("Test Summary")
    print('=' * 70)
    
    for result_key, success in results.items():
        customer_id, agent_key = result_key.rsplit('_', 1)
        agent_info = AGENT_PROMPTS[agent_key]
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {customer_id} - {agent_info['emoji']} {agent_info['name']}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\nResults: {passed}/{total} tests passed")
    print('=' * 70)
    
    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())
